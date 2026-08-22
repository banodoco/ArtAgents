"""S1 Supabase-export leg: documented envelope acceptance, NO network.

Proves the import path accepts the documented export envelope —
``VersionedTimelineEvent.to_append_json_obj()``: a TimelineEvent JSON
object plus a 1-based contiguous ``version`` key (per-timeline, ``prev_hash``
chain), exactly the ``p_events`` payload of the ``append_timeline_event``
RPC — and asserts the same zero-loss invariants (a)-(f), with the marker's
``source`` being ``supabase_export``.

Two feed paths are proven:

1. file-backed: a version-ordered export file parsed by
   :class:`SupabaseExportReader`;
2. mocked transport: the same export events delivered through a
   ``SupabaseBackend`` with an injected static transport (the
   ``tests/timeline/test_transfer.py`` mock pattern) via
   :func:`load_supabase_backend_source`.

The single remaining operational step (live export of the deployed
Supabase ``public.timeline_events`` rows) is documented in the backfill
module and CLI help; no credentials exist on this box and none are read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.receipts.canonical import canonical_json
from astrid.core.timeline.eventlog.supabase import SupabaseBackend
from astrid.packs.timeline.backfill import (
    BackfillSourceError,
    SupabaseExportReader,
    backfill_project,
    backfill_timeline,
    load_supabase_backend_source,
    load_supabase_export_source,
)
from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

from ._backfill_helpers import (
    head_seq,
    kernel_event_rows,
    make_backfill_deps,
    make_project,
    make_source_timeline,
    make_writer,
    marker_state,
    project_root_with_timeline,
)

EXPORT_SPEC = [
    ("timeline.created", {"timeline_id": "X", "slug": "cloud", "name": "Cloud"}, "human"),
    ("timeline.config_replaced", {"config": {"tracks": [], "clips": []}}, "human"),
    ("timeline.asset_registry_replaced", {"registry": {"assets": {"hero": {"file": "hero.png"}}}}, "agent"),
    ("timeline.custom_marker", {"marker": "unregistered kind raw dict"}, "system"),
]


def _write_export(path: Path, timeline_id: str) -> None:
    """Write a version-ordered export file in the documented envelope."""
    home, _tid, _ulid = make_source_timeline(
        path.parent / "src",
        timeline_id=timeline_id,
        timeline_ulid="01J00000000000000000000007",
        slug="cloud",
        name="Cloud",
        events_spec=EXPORT_SPEC,
    )
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

    events = LocalFsBackend(
        timeline_id=timeline_id, timeline_home=home
    ).read_events()
    lines = []
    for index, event in enumerate(events, start=1):
        obj = event.to_json_obj()
        obj["version"] = index
        lines.append(json.dumps(obj))
    path.write_text("\n".join(lines) + "\n")


class _StaticSupabaseTransport:
    """Static mock of the SupabaseEventLogTransport read surface.

    Returns a fixed event list (the export events) — the test_transfer
    mocked-transport pattern, restricted to the reads the import uses,
    including ``verify_chain`` (the W5 fail-closed envelope requires the
    transport seam to verify its chain before a source is built).
    """

    def __init__(self, events) -> None:
        self._events = events

    def read_events(
        self,
        *,
        timeline_id: str | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> object:
        return list(self._events)

    def verify_chain(self, *, timeline_id: str | None = None) -> object:
        from astrid.core.timeline.eventlog.types import EventLogVerification
        from astrid.core.timeline.events.schema import with_event_hash

        events = self._events
        prev_hash: str | None = None
        for index, event in enumerate(events):
            expected = with_event_hash(
                type(event).from_dict(
                    {**event.to_json_obj(), "hash": None}
                ),
                prev_hash=prev_hash,
            )
            if event.prev_hash != prev_hash or event.hash != expected.hash:
                return EventLogVerification(
                    ok=False,
                    checked_events=index,
                    last_event_id=None,
                    error=(
                        f"chain link broken at version {index + 1} "
                        f"(event {event.event_id})"
                    ),
                )
            prev_hash = event.hash
        return EventLogVerification(
            ok=True,
            checked_events=len(events),
            last_event_id=events[-1].event_id if events else None,
            error=None,
        )


def _import_source(tmp_path: Path, source, *, project_slug: str = "proj"):
    """Fresh DB + project + import of one source; writer left open."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    writer = make_writer(db_path)
    make_project(writer, slug=project_slug)
    projects, receipts, _ = make_backfill_deps(writer)
    report = backfill_timeline(
        writer=writer,
        projects=projects,
        receipts=receipts,
        project_slug=project_slug,
        source=source,
        projects_root=projects_root,
    )
    return report, source, writer, projects_root


def test_supabase_export_file_invariants(tmp_path: Path) -> None:
    timeline_id = "11111111-1111-1111-1111-111111111111"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)

    source = load_supabase_export_source(export, timeline_id=timeline_id)
    assert source.source_name == "supabase_export"
    assert source.head_version == 4 == len(source.events)

    report, source, writer, projects_root = _import_source(tmp_path, source)
    try:
        body = report.to_dict()
        assert body["source_event_count"] == 4 == body["kernel_event_count"]
        assert body["source_head_version"] == 4 == body["kernel_head_seq"]
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert body["kinds"]["timeline.custom_marker"] == 1
        assert body["kinds"]["timeline.config_replaced"] == 1
        assert body["marker_written"] is True
        state = marker_state(projects_root)
        assert state[timeline_id]["source"] == "supabase_export"
        assert state[timeline_id]["source_head_version"] == 4
        assert state[timeline_id]["events_sha256"] == source.events_sha256

        # (c) content projection, canonical per event.
        stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
        rows = kernel_event_rows(writer, stream_id)
        assert len(rows) == 4
        for index, (src_event, row) in enumerate(
            zip(source.events, rows), start=1
        ):
            assert row["seq"] == index
            assert row["kind"] == src_event.kind
            assert row["event_id"] == src_event.event_id
            from astrid.packs.timeline.backfill import map_source_event

            mapped = map_source_event(
                src_event, timeline_ulid=source.timeline_ulid
            )
            assert canonical_json(row["data"]) == canonical_json(
                mapped.expected_kernel_data
            )
    finally:
        writer.close()


def test_supabase_export_mocked_transport(tmp_path: Path) -> None:
    """The import path accepts a mocked transport (test_transfer pattern)."""
    timeline_id = "22222222-2222-2222-2222-222222222222"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)

    reader = SupabaseExportReader(export, timeline_id=timeline_id)
    backend = SupabaseBackend(
        timeline_id=timeline_id,
        transport=_StaticSupabaseTransport(reader.read_events()),
    )
    source = load_supabase_backend_source(backend, timeline_id=timeline_id)
    assert source.source_name == "supabase_export"
    assert source.head_version == 4

    report, _source, writer, projects_root = _import_source(tmp_path, source)
    try:
        body = report.to_dict()
        assert body["kernel_event_count"] == 4
        assert body["kernel_head_seq"] == 4
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert body["kinds"]["timeline.custom_marker"] == 1
        assert marker_state(projects_root)[timeline_id]["source"] == (
            "supabase_export"
        )
    finally:
        writer.close()


def test_supabase_export_idempotent_reimport(tmp_path: Path) -> None:
    timeline_id = "33333333-3333-3333-3333-333333333333"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)

    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    writer = make_writer(db_path)
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        source = load_supabase_export_source(export, timeline_id=timeline_id)
        stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
        report1 = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        assert report1.written is True
        before = kernel_event_rows(writer, stream_id)

        report2 = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
        )
        assert report2.replayed is True
        assert len(kernel_event_rows(writer, stream_id)) == len(before) == 4
        assert head_seq(writer, stream_id) == 4
    finally:
        writer.close()


def test_supabase_export_rejects_version_gap(tmp_path: Path) -> None:
    timeline_id = "44444444-4444-4444-4444-444444444444"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    lines = export.read_text().splitlines()
    # Corrupt the second line's version (1 -> 3) breaking contiguity.
    broken = json.loads(lines[1])
    broken["version"] = 3
    lines[1] = json.dumps(broken)
    export.write_text("\n".join(lines) + "\n")
    with pytest.raises(BackfillSourceError, match="1-based contiguous"):
        load_supabase_export_source(export, timeline_id=timeline_id)


def test_supabase_export_reader_requires_positive_version(
    tmp_path: Path,
) -> None:
    timeline_id = "55555555-5555-5555-5555-555555555555"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    lines = export.read_text().splitlines()
    broken = json.loads(lines[0])
    broken["version"] = 0
    lines[0] = json.dumps(broken)
    export.write_text("\n".join(lines) + "\n")
    with pytest.raises(BackfillSourceError, match="no positive version"):
        load_supabase_export_source(export, timeline_id=timeline_id)


def test_supabase_export_project_run_cli_path(tmp_path: Path) -> None:
    """backfill_project(from_supabase_export=...) — the CLI service path —
    imports a JSONL export with the same invariants."""
    timeline_id = "66666666-6666-6666-6666-666666666666"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)

    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    writer = make_writer(db_path)
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        reports = backfill_project(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            from_supabase_export=str(export),
            projects_root=projects_root,
        )
        assert set(reports) == {timeline_id}
        body = reports[timeline_id].to_dict()
        assert body["source"] == "supabase_export"
        assert body["kernel_event_count"] == 4
        assert body["kernel_head_seq"] == 4
        assert body["checks"] == {
            "count": True,
            "head": True,
            "content": True,
            "kinds": True,
            "projections": True,
        }
        assert body["kinds"]["timeline.custom_marker"] == 1
        assert marker_state(projects_root)[timeline_id]["source"] == (
            "supabase_export"
        )
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# W5 — fail-closed export envelope
# ---------------------------------------------------------------------------


def test_supabase_export_rejects_empty_export(tmp_path: Path) -> None:
    """W5: an export with no rows is rejected, never silently imported."""
    timeline_id = "77777777-7777-7777-7777-777777777777"
    export = tmp_path / "empty-export.jsonl"
    export.write_text("")
    with pytest.raises(
        BackfillSourceError, match="export contains no rows"
    ):
        load_supabase_export_source(export, timeline_id=timeline_id)


def test_supabase_export_project_scan_rejects_empty_export(
    tmp_path: Path,
) -> None:
    """W5: the project-run scanner rejects an empty export the same way."""
    timeline_id = "88888888-8888-8888-8888-888888888888"
    export = tmp_path / "empty-export.jsonl"
    export.write_text("")
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    writer = make_writer(db_path)
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        with pytest.raises(
            BackfillSourceError, match="export contains no rows"
        ):
            backfill_project(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                from_supabase_export=str(export),
                projects_root=projects_root,
            )
    finally:
        writer.close()


def test_supabase_export_rejects_broken_chain_naming_version(
    tmp_path: Path,
) -> None:
    """W5: a broken hash chain rejects the WHOLE export naming the failing
    version, before any source is built."""
    timeline_id = "99999999-9999-9999-9999-999999999999"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    lines = export.read_text().splitlines()
    broken = json.loads(lines[1])  # version 2
    broken["hash"] = "0" * 64
    lines[1] = json.dumps(broken)
    export.write_text("\n".join(lines) + "\n")
    with pytest.raises(
        BackfillSourceError,
        match="chain verification failed",
    ) as excinfo:
        load_supabase_export_source(export, timeline_id=timeline_id)
    message = str(excinfo.value)
    assert "version 2" in message
    assert timeline_id in message


def test_supabase_export_rejects_malformed_row_naming_index(
    tmp_path: Path,
) -> None:
    """W5: a non-object row rejects the whole export naming its index."""
    timeline_id = "aaaaaa11-1111-1111-1111-111111111111"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    export.write_text(export.read_text() + "42\n")
    with pytest.raises(
        BackfillSourceError, match="not a JSON object"
    ) as excinfo:
        load_supabase_export_source(export, timeline_id=timeline_id)
    assert "item 4" in str(excinfo.value)


def test_supabase_export_rejects_row_missing_timeline_id_naming_index(
    tmp_path: Path,
) -> None:
    """W5: a row missing timeline_id rejects the whole export (no silent
    skip in the scanner)."""
    timeline_id = "aaaaaa22-2222-2222-2222-222222222222"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    lines = export.read_text().splitlines()
    broken = json.loads(lines[0])
    del broken["timeline_id"]
    lines[0] = json.dumps(broken)
    export.write_text("\n".join(lines) + "\n")
    with pytest.raises(
        BackfillSourceError, match="has no timeline_id"
    ) as excinfo:
        load_supabase_export_source(export, timeline_id=timeline_id)
    assert "item 0" in str(excinfo.value)


def test_supabase_export_project_scan_rejects_malformed_row(
    tmp_path: Path,
) -> None:
    """W5: the project-run scanner rejects a malformed row for the whole
    export naming its index — no silent skips anywhere in the scanner."""
    timeline_id = "aaaaaa33-3333-3333-3333-333333333333"
    export = tmp_path / "export.jsonl"
    _write_export(export, timeline_id)
    export.write_text(export.read_text() + '"not-an-object"\n')
    projects_root = tmp_path / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    writer = make_writer(db_path)
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        with pytest.raises(
            BackfillSourceError, match="not a JSON object"
        ) as excinfo:
            backfill_project(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                from_supabase_export=str(export),
                projects_root=projects_root,
            )
        assert "item 4" in str(excinfo.value)
    finally:
        writer.close()
