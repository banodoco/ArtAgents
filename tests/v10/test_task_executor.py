"""Kernel task-executor service and in-UoW media materialization tests.

T16 (m2 plan step 9) proves the injected local-handler boundary:
``ExecutionService.execute`` starts the fenced attempt and records its
staging id through the caller-owned UoW, runs the handler outside SQLite,
validates the exact result manifest, prepares media descriptors, and routes
handler errors through the repository failure command — without importing
packs or adding remote execution.

T17 (m2 plan step 10) proves the receipt-less in-UoW media primitive
``MediaRepository.materialize_prepared``: verified bytes are published (or
reused) and media/location/relation/stream/event/head state is created
inside an existing caller UoW with same-project and deterministic ordering
guarantees and no separate receipt.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORTED_EVENT_KIND,
    CORE_MEDIA_RELATED_EVENT_KIND,
    CORE_MEDIA_STREAM_TYPE,
    MANAGED_LOCAL_REALM,
    MediaRepository,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_FAILED_EVENT_KIND,
    CORE_TASK_STARTED_EVENT_KIND,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.task_executor import (
    STAGING_TXN_ID_KEY,
    ExecutionResult,
    ExecutionService,
    PreparedExecution,
    PreparedOutput,
)
from astrid.core.util.time import utc_now_iso

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

SPEC_A = {"backend": "remotion", "composition": "main", "fps": 24}
MANIFEST_A = ["media_1", "media_2"]


@pytest.fixture
def env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project/task/media repositories over one root."""
    from types import SimpleNamespace

    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "executor_env.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            task_repo=TaskRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
        )
    finally:
        writer.close()


def _create_project(env, *, slug: str = "pilot", project_id: str | None = None):
    args = {
        "slug": slug,
        "name": slug.title(),
        "settings": {"fps": 24},
        "idempotency_key": f"create-{slug}-k",
        "project_id": project_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(lambda u: env.project_repo.create(u, **args))


def _admit(
    env,
    *,
    project_id: str,
    task_id: str | None = None,
    max_attempts: int = 2,
    **overrides,
):
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": "rendering.timeline_visualize",
        "spec": dict(SPEC_A),
        "input_manifest": list(MANIFEST_A),
        "idempotency_key": f"admit-{task_id}-k",
        "task_id": task_id,
        "max_attempts": max_attempts,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.create(u, **args))


def _claim(env, *, project_id: str, idempotency_key: str = "claim-k", **overrides):
    args = {
        "project_id": project_id,
        "idempotency_key": idempotency_key,
        "executor_id": "executor-1",
        "now": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.claim(u, **args))


def _attempt_row(writer: DatabaseWriter, attempt_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM execution_attempts WHERE id = ?", (attempt_id,)
        )
    )


def _task_row(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
    )


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )


def _receipt_count(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM command_receipts WHERE project_id = ?",
            (project_id,),
        )[0]
    )


def _project_head(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )[0]
    )


def _stream_head(writer: DatabaseWriter, stream_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
        )[0]
    )


def _sha256_hex(path: Path) -> str:
    from astrid.core.io.media_import import sha256_file_bytes

    return sha256_file_bytes(path)


# ---------------------------------------------------------------------------
# Fake handler + manifest builder
# ---------------------------------------------------------------------------


class FakeHandler:
    """Writes concrete files under staging and returns a result manifest."""

    def __init__(
        self,
        files: dict[str, bytes],
        *,
        error: BaseException | None = None,
        manifest_override=None,
        probe=None,
    ) -> None:
        self._files = files
        self._error = error
        self._manifest_override = manifest_override
        self.probe = probe
        self.calls: list[tuple[object, Path]] = []

    def execute(self, *, task, staging_dir: Path):
        self.calls.append((task, staging_dir))
        if self._error is not None:
            raise self._error
        for name, content in self._files.items():
            (staging_dir / name).write_bytes(content)
        if self._manifest_override is not None:
            return self._manifest_override
        outputs = []
        for index, name in enumerate(sorted(self._files)):
            path = staging_dir / name
            outputs.append(
                {
                    "path": name,
                    "content_hash": f"sha256:{_sha256_hex(path)}",
                    "bytes": path.stat().st_size,
                    "ordinal": index,
                    "is_primary": index == 0,
                    "role": "result" if index == 0 else None,
                }
            )
        return {
            "schema_version": 1,
            "kind": "rendering.timeline_visualize",
            "inputs": {"task_id": task.id},
            "outputs": outputs,
            "created": TS2,
            "warnings": [],
        }


# ---------------------------------------------------------------------------
# T16: execution service boundary
# ---------------------------------------------------------------------------


def _execute(env, *, project_id, claim, handler, **overrides):
    service = ExecutionService(
        projects_root=env.projects_root, task_repo=env.task_repo
    )
    args = {
        "project_id": project_id,
        "task_id": claim.task.id,
        "attempt_id": claim.attempt.id,
        "lease_id": claim.attempt.lease_id,
        "expected_status_version": claim.attempt.status_version,
        "idempotency_key": "execute-k",
        "handler": handler,
        "now": TS2,
    }
    args.update(overrides)
    uow = UnitOfWork(env.writer)
    return service.execute(uow, **args)


def test_execute_prepares_media_descriptors_from_handler_outputs(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id)
    claim = _claim(env, project_id=project.id)
    assert claim is not None

    handler = FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"})
    result = _execute(env, project_id=project.id, claim=claim, handler=handler)
    assert result.outcome == "prepared"
    assert isinstance(result.prepared, PreparedExecution)
    prepared = result.prepared

    # The attempt is running with the staging id recorded as runtime state.
    assert prepared.attempt.status == "running"
    assert prepared.attempt.status_version == 2
    row = _attempt_row(env.writer, prepared.attempt.id)
    progress = json.loads(row["progress_json"])
    assert progress[STAGING_TXN_ID_KEY] == prepared.staging_txn_id
    assert re.fullmatch(r"[0-9a-f]{32}", prepared.staging_txn_id)
    assert _task_row(env.writer, task.id)["status"] == "running"

    # The staging directory exists under the frozen staging layout and the
    # handler saw the running task model plus the assigned directory.
    assert prepared.staging_dir == (
        env.projects_root / ".astrid" / "media" / ".staging" / prepared.staging_txn_id
    )
    assert prepared.staging_dir.is_dir()
    assert (prepared.staging_dir / "frame.svg").is_file()
    assert handler.calls[0][0].id == task.id
    assert handler.calls[0][0].status == "running"
    assert handler.calls[0][1] == prepared.staging_dir

    # Every validated output has an immutable prepared media descriptor with
    # the exact byte digest (hashing ran outside SQLite).
    assert len(prepared.outputs) == 2
    by_path = {out.path: out for out in prepared.outputs}
    assert set(by_path) == {"frame.svg", "story.md"}
    frame = by_path["frame.svg"]
    assert isinstance(frame, PreparedOutput)
    assert frame.is_primary is True
    assert frame.ordinal == 0
    assert frame.prepared.digest == _sha256_hex(prepared.staging_dir / "frame.svg")
    assert frame.prepared.rel_path == "frame.svg"
    assert frame.prepared.media_kind in (
        "vector",
        "image",
        "text",
        "document",
        "video",
        "audio",
        "other",
    )
    assert prepared.manifest.outputs[0].path == "frame.svg"

    # The start event exists; no completion/terminal state was written.
    stream_id = f"{task.id}:core.task"
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_STARTED_EVENT_KIND


def test_execute_records_staging_id_visible_to_startup_gc(env) -> None:
    """The recorded staging id is exactly what startup GC treats as live."""
    from astrid.packs import LIVE_ATTEMPT_STAGING_KEY, collect_live_staging_txn_ids

    assert STAGING_TXN_ID_KEY == LIVE_ATTEMPT_STAGING_KEY
    project = _create_project(env)
    _admit(env, project_id=project.id)
    claim = _claim(env, project_id=project.id)
    assert claim is not None
    result = _execute(
        env,
        project_id=project.id,
        claim=claim,
        handler=FakeHandler({"out.png": b"\x89PNG"}),
    )
    assert result.outcome == "prepared"
    assert result.prepared is not None
    live = collect_live_staging_txn_ids(env.writer)
    assert result.prepared.staging_txn_id in live
    assert result.prepared.staging_dir.is_dir()


def test_handler_runs_outside_sqlite_transactions(env) -> None:
    """No BEGIN IMMEDIATE is open while the handler executes."""
    project = _create_project(env)
    _admit(env, project_id=project.id)
    claim = _claim(env, project_id=project.id)
    assert claim is not None

    observed: dict[str, object] = {}

    class ProbingHandler(FakeHandler):
        def execute(self, *, task, staging_dir):
            observed["in_transaction"] = env.writer.submit(
                lambda session: session.in_transaction
            )
            return super().execute(task=task, staging_dir=staging_dir)

    result = _execute(
        env,
        project_id=project.id,
        claim=claim,
        handler=ProbingHandler({"out.txt": b"x"}),
    )
    assert result.outcome == "prepared"
    assert observed["in_transaction"] is False


def test_handler_error_routes_through_failure_command(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id, max_attempts=2)
    claim = _claim(env, project_id=project.id)
    assert claim is not None
    receipts_before = _receipt_count(env.writer, project.id)

    result = _execute(
        env,
        project_id=project.id,
        claim=claim,
        handler=FakeHandler({}, error=RuntimeError("renderer boom")),
    )
    assert result.outcome == "failed"
    assert result.error == {
        "reason": "handler_failed",
        "type": "RuntimeError",
        "message": "renderer boom",
    }
    assert result.failure is not None
    assert result.failure.outcome == "requeued"  # budget remains
    assert result.failure.task.status == "queued"
    assert result.failure.attempt.status == "failed"
    assert result.failure.attempt.error == {
        "reason": "handler_failed",
        "type": "RuntimeError",
        "message": "renderer boom",
    }
    assert _receipt_count(env.writer, project.id) == receipts_before + 2  # start + fail

    stream_id = f"{task.id}:core.task"
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_FAILED_EVENT_KIND


def test_invalid_manifest_routes_through_failure_command(env) -> None:
    project = _create_project(env)
    task = _admit(env, project_id=project.id, max_attempts=2)
    claim = _claim(env, project_id=project.id)
    assert claim is not None

    handler = FakeHandler(
        {"frame.svg": b"<svg/>"},
        manifest_override={
            "schema_version": 1,
            "kind": "rendering.timeline_visualize",
            "inputs": {},
            "outputs": [
                {
                    "path": "missing.svg",  # declared but never written
                    "content_hash": f"sha256:{'0' * 64}",
                    "bytes": 4,
                    "ordinal": 0,
                    "is_primary": True,
                }
            ],
            "created": TS2,
            "warnings": [],
        },
    )
    result = _execute(env, project_id=project.id, claim=claim, handler=handler)
    assert result.outcome == "failed"
    assert result.error is not None
    assert result.error["reason"] == "handler_failed"
    assert result.failure is not None
    assert result.failure.outcome == "requeued"
    assert _task_row(env.writer, task.id)["status"] == "queued"


def test_stale_start_surfaces_typed_repository_outcome(env) -> None:
    project = _create_project(env)
    _admit(env, project_id=project.id)
    claim = _claim(env, project_id=project.id)
    assert claim is not None
    receipts_before = _receipt_count(env.writer, project.id)

    from astrid.core.repositories.tasks import TaskTransitionError

    service = ExecutionService(
        projects_root=env.projects_root, task_repo=env.task_repo
    )
    uow = UnitOfWork(env.writer)
    with pytest.raises(TaskTransitionError) as excinfo:
        service.execute(
            uow,
            project_id=project.id,
            task_id=claim.task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=7,  # stale
            idempotency_key="execute-stale-k",
            handler=FakeHandler({"out.txt": b"x"}),
            now=TS2,
        )
    assert excinfo.value.reason == "stale_status_version"
    assert _receipt_count(env.writer, project.id) == receipts_before
    assert _task_row(env.writer, claim.task.id)["status"] == "running"


def test_service_source_stays_free_of_packs_and_remote_execution(env) -> None:
    """Kernel boundary: no pack import and no remote/provider path."""
    from astrid.core import task_executor as package
    from astrid.core.task_executor import service as module

    source = (
        Path(module.__file__).read_text(encoding="utf-8")
        + Path(package.__file__).read_text(encoding="utf-8")
    )
    assert "astrid.packs" not in source
    assert "import astrid.core.execution" not in source
    for forbidden in (
        "urllib",
        "requests",
        "socket",
        "openai",
        "fal",
        "subprocess",
    ):
        assert forbidden not in source, f"remote/provider path leaked: {forbidden}"


# ---------------------------------------------------------------------------
# T17: in-UoW media materialization primitive (no separate receipt)
# ---------------------------------------------------------------------------


def _materialize(env, *, project_id, name, content, relations=None, **overrides):
    from astrid.core.io.media_import import prepare_media_file

    staging = env.projects_root / ".astrid" / "media" / ".staging" / "mat"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / name
    path.write_bytes(content)
    prepared = prepare_media_file(path, root=staging)
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": f"materialize-{name}-k",
        "created_at": TS2,
    }
    if relations is not None:
        args["relations"] = relations
    args.update(overrides)

    def run(u: UnitOfWork):
        return env.media_repo.materialize_prepared(u, **args)

    return UnitOfWork(env.writer).run(run)


def test_materialize_prepared_creates_media_state_without_separate_receipt(
    env,
) -> None:
    project = _create_project(env)
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    materialized = _materialize(
        env, project_id=project.id, name="frame.svg", content=b"<svg/>"
    )
    assert materialized.media_id
    assert materialized.event_id
    assert materialized.stream_id == (
        f"{materialized.media_id}:{CORE_MEDIA_STREAM_TYPE}"
    )

    # No separate receipt: the helper writes no receipt of its own; the
    # caller's completion command owns the single receipt.
    assert _receipt_count(env.writer, project.id) == receipts_before
    # One event and one head advance (project + stream).
    assert _project_head(env.writer, project.id) == head_before + 1
    assert _stream_head(env.writer, materialized.stream_id) == 1
    events = _event_rows(env.writer, materialized.stream_id)
    assert events[-1]["kind"] == CORE_MEDIA_IMPORTED_EVENT_KIND

    # Media + managed location rows exist with byte identity.
    media = env.media_repo.show(env.writer, materialized.media_id)
    assert media.project_id == project.id
    assert media.content_hash == _sha256_hex(
        env.projects_root / ".astrid" / "media" / "sha256"
        / media.content_hash[:2] / media.content_hash[2:4] / media.content_hash
    )
    assert len(media.locations) == 1
    assert media.locations[0].realm == MANAGED_LOCAL_REALM


def test_materialize_prepared_dedupes_and_orders_deterministically(env) -> None:
    project = _create_project(env)
    first = _materialize(env, project_id=project.id, name="a.svg", content=b"<svg/>")
    head_after_first = _project_head(env.writer, project.id)

    # Same bytes again: the media row and managed location are reused, one
    # more imported event is appended in deterministic order.
    second = _materialize(env, project_id=project.id, name="b.svg", content=b"<svg/>")
    assert second.media_id == first.media_id
    assert second.project_seq == head_after_first + 1
    assert _project_head(env.writer, project.id) == head_after_first + 1
    assert len(env.media_repo.show(env.writer, first.media_id).locations) == 1


def test_materialize_prepared_rejects_cross_project_media_id(env) -> None:
    other = _create_project(env, slug="other", project_id=generate_lowercase_ulid())
    first_project = _create_project(env, slug="first")
    media_id = generate_lowercase_ulid()
    _materialize(
        env, project_id=first_project.id, name="a.svg", content=b"<svg/>",
        media_id=media_id,
    )
    from astrid.core.repositories.media import MediaConflictError

    with pytest.raises(MediaConflictError):
        _materialize(
            env, project_id=other.id, name="b.svg", content=b"<svg/>",
            media_id=media_id,
        )


def test_materialize_prepared_materializes_relations_in_ordinal_order(env) -> None:
    project = _create_project(env)
    primary = _materialize(
        env, project_id=project.id, name="primary.png", content=b"\x89PNG"
    )
    variant = _materialize(
        env, project_id=project.id, name="variant.png", content=b"\x89PNG2"
    )
    head_before = _project_head(env.writer, project.id)

    relations = [
        {
            "from_media_id": variant.media_id,
            "to_media_id": primary.media_id,
            "kind": "variant_of",
            "ordinal": 0,
        }
    ]
    result = _materialize(
        env,
        project_id=project.id,
        name="extra.svg",
        content=b"<svg/>",
        relations=relations,
    )
    assert len(result.relations) == 1
    assert result.relations[0].from_media_id == variant.media_id
    assert result.relations[0].kind == "variant_of"

    # Two more events (imported + related) in deterministic order and no
    # separate receipt.
    assert _project_head(env.writer, project.id) == head_before + 2
    variant_stream = f"{variant.media_id}:{CORE_MEDIA_STREAM_TYPE}"
    related = _event_rows(env.writer, variant_stream)
    assert related[-1]["kind"] == CORE_MEDIA_RELATED_EVENT_KIND
    data = json.loads(related[-1]["payload_json"])["data"]
    assert data["from_media_id"] == variant.media_id
    assert data["to_media_id"] == primary.media_id


def test_materialize_prepared_rejects_bad_relations_before_sql(env) -> None:
    project = _create_project(env)
    primary = _materialize(
        env, project_id=project.id, name="primary.png", content=b"\x89PNG"
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    from astrid.core.repositories.media import MediaRelationError

    # Unknown relation kind: rejected before any SQL.
    with pytest.raises(MediaRelationError) as excinfo:
        _materialize(
            env,
            project_id=project.id,
            name="bad.svg",
            content=b"<svg/>",
            relations=[
                {
                    "from_media_id": primary.media_id,
                    "to_media_id": primary.media_id,
                    "kind": "self_link",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "kind"
    # Self-link rejected.
    with pytest.raises(MediaRelationError) as excinfo:
        _materialize(
            env,
            project_id=project.id,
            name="bad2.svg",
            content=b"<svg2/>",
            relations=[
                {
                    "from_media_id": primary.media_id,
                    "to_media_id": primary.media_id,
                    "kind": "variant_of",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "self"
    assert _receipt_count(env.writer, project.id) == receipts_before
    assert _project_head(env.writer, project.id) == head_before
