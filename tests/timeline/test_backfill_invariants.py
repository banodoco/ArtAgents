"""S1 zero-loss invariant suite for the SQLite-cutover backfill.

Covers the reusable checker (a)-(g) plus the marker discipline (f):

a. expected event count == kernel event count for the mapped stream
   (source + synthesized bootstrap, W3);
b. head continuity: ``event_streams.head_seq`` == source version +
   ``synthesized_count``;
c. content projection: canonical equality of every preserved field
   (kind, payload data, actor_kind, created_at, event_id) plus the
   mapper-derived txn_id and changes_json (W4);
d. idempotency: the same import twice yields ZERO new kernel events and an
   unchanged head;
e. unknown-kind pass-through: per-kind counts preserved, including kinds the
   timeline schema does not register;
f. marker written only after all checks pass; a failed import writes no
   marker and leaves no partial authority claim;
g. stored whole-document projections equal the source-side projections
   (verify what you serve, W4).

Plus the G1 rework proofs: crash-convergent commit->verify->marker (W1),
paged verification beyond 10k events (W1.2), bootstrap synthesis for
slices without ``timeline.created`` (W3), tamper probes (W4), honest
dry-run (W6), and the bridge-parity regression (W7c).
"""

from __future__ import annotations

import shutil
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
    load_source,
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
        "projections": True,
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
        "projections": True,
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
        "synthesized_bootstrap": False,
    }
    assert set(state[timeline_id].keys()) == {
        "backfilled_at",
        "source",
        "source_head_version",
        "events_sha256",
        "synthesized_bootstrap",
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
        assert body["evaluated"] is False
        assert body["written"] is False
        assert body["marker_written"] is False
        assert body["kernel_event_count"] == 0
        assert body["kernel_head_seq"] == 0
        assert body["source_event_count"] == 6
        assert body["source_head_version"] == 6
        # Honest dry-run (W6): target-side checks are None (not evaluated),
        # never hardcoded trues.
        assert body["checks"] == {
            "count": None,
            "head": None,
            "content": None,
            "kinds": None,
            "projections": None,
        }
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


# ---------------------------------------------------------------------------
# W1 — crash-convergent commit -> verify -> marker
# ---------------------------------------------------------------------------


def test_interruption_converges_to_exact_states(tmp_path: Path) -> None:
    """W1.4: after ANY interruption the state is exactly {nothing written}
    or {events + receipt + marker, fully verified}; a retry converges."""
    projects_root, home, timeline_id, _ulid = project_root_with_timeline(
        tmp_path
    )
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        source = load_source(home)
        stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"

        # --- Transition point 1: pre-append crash (mid-transaction) -------
        def _explode(_index: int) -> None:
            raise RuntimeError("simulated process kill mid-transaction")

        with pytest.raises(RuntimeError, match="simulated process kill"):
            backfill_timeline(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                source=source,
                projects_root=projects_root,
                on_before_append=_explode,
            )
        import sqlite3

        conn = sqlite3.connect(
            projects_root / ".astrid" / "astrid.sqlite3"
        )
        try:
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

        # Retry (no crash) converges to {events + receipt + marker, fully
        # verified}.
        report = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        assert report.written is True
        assert report.marker_written is True
        assert report.to_dict()["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert head_seq(writer, stream_id) == 6
        assert verify_backfill(
            source, stream_id=stream_id, writer=writer
        ).ok is True

        # --- Transition point 2: post-commit/pre-marker crash -------------
        marker_path = projects_root / ".astrid" / "backfill-state.json"
        marker_path.unlink()  # committed receipt+events; marker never landed
        assert marker_json(projects_root) == {}
        report2 = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        # W1.3 complete-the-marker: retry re-verifies and refreshes the
        # marker instead of raising BackfillAuthorityError.
        assert report2.replayed is True
        assert report2.to_dict()["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert marker_state(projects_root)[timeline_id]["events_sha256"] == (
            source.events_sha256
        )
        # Zero new rows: the retry replayed the committed import.
        assert len(kernel_event_rows(writer, stream_id)) == 6
        assert head_seq(writer, stream_id) == 6
        assert verify_backfill(
            source, stream_id=stream_id, writer=writer
        ).ok is True
    finally:
        writer.close()


def test_marker_crash_retry_converges(tmp_path: Path) -> None:
    """W1.3 marker convergence, quoted: crash-after-commit-before-marker
    retried with the identical source converges to marker present and every
    check true (no BackfillAuthorityError, no new rows)."""
    report, source, writer, projects_root, stream_id, timeline_id = _import(
        tmp_path
    )
    assert report.marker_written is True
    # Simulate the crash: committed receipt/stream/events exist, the marker
    # file never landed.
    (projects_root / ".astrid" / "backfill-state.json").unlink()
    assert marker_json(projects_root) == {}
    projects, receipts, _ = make_backfill_deps(writer)
    try:
        retry = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        body = retry.to_dict()
        assert retry.replayed is True
        assert body["marker_written"] is True
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert marker_state(projects_root)[timeline_id]["events_sha256"] == (
            source.events_sha256
        )
        assert len(kernel_event_rows(writer, stream_id)) == 6
        assert head_seq(writer, stream_id) == 6
        assert verify_backfill(
            source, stream_id=stream_id, writer=writer
        ).ok is True
    finally:
        writer.close()


def test_paged_verification_past_ten_thousand_events(tmp_path: Path) -> None:
    """W1.2: a 10,001-event synthetic import succeeds end-to-end with paged
    verification — the old single-read 10k repository cap is gone."""
    import json as _json

    from astrid.core.timeline.events.schema import (
        TimelineActor,
        TimelineEvent,
        generate_event_ulid,
        with_event_hash,
    )
    from astrid.packs.timeline.backfill import load_supabase_export_source

    timeline_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    event_count = 10_001
    events: list[TimelineEvent] = []
    prev_hash: str | None = None
    for index in range(1, event_count + 1):
        if index == 1:
            kind = "timeline.created"
            payload = {
                "timeline_id": timeline_id,
                "slug": "big",
                "name": "Big Timeline",
            }
        else:
            kind = "timeline.config_replaced"
            payload = {"config": {"tracks": [], "clips": []}}
        event = with_event_hash(
            TimelineEvent(
                event_id=generate_event_ulid(),
                timeline_id=timeline_id,
                ts="2026-08-01T00:00:00Z",
                actor=TimelineActor(type="system", id="system:gen"),
                prev_hash=prev_hash,
                hash=None,
                kind=kind,
                payload=payload,
            ),
            prev_hash=prev_hash,
        )
        events.append(event)
        prev_hash = event.hash
    export = tmp_path / "big-export.jsonl"
    lines = []
    for index, event in enumerate(events, start=1):
        obj = event.to_json_obj()
        obj["version"] = index
        lines.append(_json.dumps(obj))
    export.write_text("\n".join(lines) + "\n")

    source = load_supabase_export_source(export, timeline_id=timeline_id)
    assert source.head_version == event_count == len(source.events)
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        report = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        body = report.to_dict()
        assert body["kernel_event_count"] == event_count
        assert body["kernel_head_seq"] == event_count
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
        import sqlite3

        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            kernel_count = conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE stream_id = ?",
                (stream_id,),
            ).fetchone()["n"]
        assert kernel_count == event_count
        assert verify_backfill(
            source, stream_id=stream_id, writer=writer
        ).ok is True
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# W3 — slice-shaped bootstrap synthesis
# ---------------------------------------------------------------------------


DESERT_SLICE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "timeline_visualize"
    / "desert_slice"
)


def _import_desert_slice(tmp_path: Path):
    """Copy the desert_slice fixture (no timeline.created) into a temp
    project root and import it; returns the report/source/writer/root."""
    projects_root = tmp_path / "projects"
    timelines_dir = projects_root / "proj" / "timelines"
    timelines_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        DESERT_SLICE, timelines_dir / "01KYPVKMW5STB4W6FE05ED8242"
    )
    (projects_root / "proj" / "project.json").write_text("{}")
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    make_project(writer)
    projects, receipts, _ = make_backfill_deps(writer)
    source = load_source(timelines_dir / "01KYPVKMW5STB4W6FE05ED8242")
    report = backfill_timeline(
        writer=writer,
        projects=projects,
        receipts=receipts,
        project_slug="proj",
        source=source,
        projects_root=projects_root,
    )
    return report, source, writer, projects_root


def test_desert_slice_synthesizes_bootstrap_and_imports(tmp_path: Path) -> None:
    """W3: a source without timeline.created gets exactly one deterministic
    synthesized bootstrap event at kernel position 0; invariant (b) holds as
    head_seq == source_version + 1; report + marker record it."""
    report, source, writer, projects_root = _import_desert_slice(tmp_path)
    try:
        body = report.to_dict()
        # Source has 159 events and NO timeline.created.
        assert source.head_version == 159
        assert body["source_head_version"] == 159
        # Exactly one synthesized bootstrap event: kernel holds 160.
        assert body["synthesized_bootstrap"] is True
        assert body["kernel_event_count"] == 160
        assert body["kernel_head_seq"] == 160
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        # The synthesized event is kernel position 0: kind timeline.created,
        # actor_kind system, created_at = first source event ts.
        stream_id = f"{source.timeline_id}:{TIMELINE_STREAM_TYPE}"
        rows = kernel_event_rows(writer, stream_id)
        assert len(rows) == 160
        created = rows[0]
        assert created["seq"] == 1
        assert created["kind"] == "timeline.created"
        assert created["actor_kind"] == "system"
        assert created["created_at"] == source.events[0].ts
        # Deterministic bootstrap: identity-ULID conventions (the identity
        # sidecar ULID for local_fs) keep the editor's ULID addressability.
        assert created["data"]["timeline_ulid"] == source.timeline_ulid
        assert created["data"]["timeline_ulid"] == (
            "01KYPVKMW5STB4W6FE05ED8242"
        )
        assert created["data"]["slug"] == "plant-growth-storyboard"
        assert created["data"]["name"] == "Desert Plant Growth Storyboard"
        # Marker records the synthesis.
        state = marker_state(projects_root)
        assert state[source.timeline_id]["synthesized_bootstrap"] is True
        assert state[source.timeline_id]["source_head_version"] == 159
        # Re-import is idempotent (zero new rows) and keeps the marker.
        projects, receipts, _ = make_backfill_deps(writer)
        report2 = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        assert report2.replayed is True
        assert len(kernel_event_rows(writer, stream_id)) == 160
    finally:
        writer.close()


def test_full_lifecycle_source_synthesizes_nothing(tmp_path: Path) -> None:
    """W3 pin: existing full-lifecycle sources synthesize NOTHING — report
    and marker both record synthesized_bootstrap false."""
    report, source, _writer, projects_root, _stream, _tid = _import(tmp_path)
    assert any(
        event.kind == "timeline.created" for event in source.events
    )
    body = report.to_dict()
    assert body["synthesized_bootstrap"] is False
    assert body["kernel_event_count"] == 6 == body["source_event_count"]
    assert marker_state(projects_root)[source.timeline_id][
        "synthesized_bootstrap"
    ] is False
    _writer.close()


# ---------------------------------------------------------------------------
# W4 — verify what you serve (projections)
# ---------------------------------------------------------------------------


def test_tampered_document_json_probe_reports_projection_mismatch(
    tmp_path: Path,
) -> None:
    """W4 probe: tamper the stored document_json post-hoc; the verifier
    names the column + index and the import fails closed."""
    report, source, writer, projects_root, stream_id, _tid = _import(tmp_path)
    writer.submit(
        lambda session: session.execute(
            "UPDATE timelines SET document_json = json_set("
            "document_json, '$.tracks', json('[]')) "
            "WHERE id = ?",
            (source.timeline_id,),
        )
    )
    try:
        verification = verify_backfill(
            source, stream_id=stream_id, writer=writer
        )
        assert verification.ok is False
        assert any(
            "document_json" in item and source.timeline_id in item
            for item in verification.projection_mismatches
        ), verification.projection_mismatches
        # A re-import replays the receipt then re-verifies and fails closed
        # naming the projection column (no marker rewrite).
        projects, receipts, _ = make_backfill_deps(writer)
        with pytest.raises(BackfillDiscrepancyError) as excinfo:
            backfill_timeline(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                source=source,
                projects_root=projects_root,
            )
        assert "document_json" in str(excinfo.value)
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# W6 — honest dry-run on a diverged existing stream
# ---------------------------------------------------------------------------


def test_dry_run_diverged_stream_reports_truthful_false(tmp_path: Path) -> None:
    """W6: dry-run against an EXISTING kernel stream with a diverged source
    runs the real read-only verifier and reports count/head false — never
    green — with evaluated true and zero writes."""
    report, source, writer, projects_root, stream_id, timeline_id = _import(
        tmp_path
    )
    assert report.to_dict()["checks"] == {
        "count": True,
        "head": True,
        "content": True,
        "kinds": True,
        "projections": True,
    }
    # Drift the source: append one more event to the JSONL home (head 6->7).
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
    from astrid.core.timeline.events.schema import TimelineActor

    home = (
        projects_root
        / "proj"
        / "timelines"
        / "01J00000000000000000000001"
    )
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
    backend.append_event(
        timeline_id,
        "timeline.config_replaced",
        {"config": {"tracks": [], "clips": []}},
        actor=TimelineActor(type="human", id="actor:human"),
    )
    drifted = load_source(home)
    assert drifted.head_version == 7

    projects, receipts, _ = make_backfill_deps(writer)
    try:
        dry = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=drifted,
            projects_root=projects_root,
            dry_run=True,
        )
        body = dry.to_dict()
        assert body["dry_run"] is True
        assert body["evaluated"] is True
        # Truthful numbers: kernel still holds 6, source now has 7.
        assert body["kernel_event_count"] == 6
        assert body["kernel_head_seq"] == 6
        assert body["source_event_count"] == 7
        assert body["source_head_version"] == 7
        # count/head/kinds report the real divergence as false (never
        # green); the projection diverges too (the appended config_replaced
        # replaced the config), while the overlapping positions 1-6 stay
        # content-true.
        assert body["checks"] == {
            "count": False,
            "head": False,
            "content": True,
            "kinds": False,
            "projections": False,
        }
        # No writes: kernel rows and marker untouched.
        assert len(kernel_event_rows(writer, stream_id)) == 6
        assert head_seq(writer, stream_id) == 6
        assert marker_state(projects_root)[timeline_id][
            "source_head_version"
        ] == 6
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# W7c — bridge parity regression (spawn-free, same adapter the bridge uses)
# ---------------------------------------------------------------------------


def test_bridge_serves_backfilled_slice_equal_to_source_projection(
    tmp_path: Path,
) -> None:
    """W7c: the repository-served projection (through the same adapter the
    bridge uses) equals the source-side projection — config, registry, and
    config_version == kernel head — for a synthesized-bootstrap slice."""
    from astrid.packs.timeline.backfill import sha256_hex
    from astrid.packs.timeline.bridge import TimelineBridgeAdapter

    report, source, writer, projects_root = _import_desert_slice(tmp_path)
    try:
        assert report.to_dict()["synthesized_bootstrap"] is True
        projects, _receipts, timelines = make_backfill_deps(writer)
        bridge = TimelineBridgeAdapter(
            writer=writer, projects=projects, timelines=timelines
        )
        load = bridge.load_timeline("proj", source.timeline_id)
        # Same adapter surface the HTTP GET serves: config/registry equality.
        assert sha256_hex(dict(load.config)) == sha256_hex(
            source.projected_config
        )
        assert sha256_hex(dict(load.registry["assets"])) == sha256_hex(
            source.projected_registry["assets"]
        )
        assert load.config_version == report.to_dict()["kernel_head_seq"] == 160
        assert load.slug == "plant-growth-storyboard"
        # The synthesized bootstrap preserved the source's identity ULID as
        # the alias metadata — no silently-substituted derived ULID.
        assert load.timeline_ulid == source.timeline_ulid
        assert load.timeline_ulid == "01KYPVKMW5STB4W6FE05ED8242"
    finally:
        writer.close()
