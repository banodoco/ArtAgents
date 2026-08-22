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
    CORE_TASK_COMPLETED_EVENT_KIND,
    CORE_TASK_FAILED_EVENT_KIND,
    CORE_TASK_STARTED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
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


# ---------------------------------------------------------------------------
# T18: fenced completion transaction (plan step 10)
# ---------------------------------------------------------------------------


def _prepare_output(env, *, name: str, content: bytes, **overrides):
    """Prepare one PreparedMedia record under a fresh staging directory."""
    from astrid.core.io.media_import import prepare_media_file

    staging = env.projects_root / ".astrid" / "media" / ".staging" / f"t18-{name}"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / name
    path.write_bytes(content)
    prepared = prepare_media_file(path, root=staging)
    entry = {
        "ordinal": 0,
        "is_primary": True,
        "role": "result",
        "label": name,
        "path": name,
        "prepared": prepared,
    }
    entry.update(overrides)
    return entry


def _evidence_output(**overrides):
    """One evidence output entry: declared facts, no prepared media."""
    entry = {
        "ordinal": 0,
        "is_primary": True,
        "role": "result",
        "path": "report.json",
        "digest": "sha256:" + "a" * 64,
        "byte_size": 128,
        "label": "report",
    }
    entry.update(overrides)
    return entry


def _started_attempt(env, *, project_id: str, idempotency_key: str = "t18-claim-k"):
    """Admit, claim, and start one task; return (task, claim, started)."""
    task = _admit(env, project_id=project_id, max_attempts=2)
    claim = _claim(env, project_id=project_id, idempotency_key=idempotency_key)
    assert claim is not None and claim.task.id == task.id
    started = UnitOfWork(env.writer).run(
        lambda u: env.task_repo.start(
            u,
            project_id=project_id,
            task_id=task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=1,
            idempotency_key=f"{idempotency_key}:start",
            now=TS,
        )
    )
    return task, claim, started


def _complete(env, *, project_id, task_id, attempt_id, lease_id, status_version,
              outputs, key="t18-complete-k", **overrides):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
        "expected_status_version": status_version,
        "idempotency_key": key,
        "outputs": outputs,
        "media_repo": env.media_repo,
        "now": TS2,
    }
    args.update(overrides)

    def run(u):
        return env.task_repo.complete(u, **args)

    return UnitOfWork(env.writer).run(run)


def _task_output_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM task_outputs WHERE task_id = ? ORDER BY ordinal ASC",
            (task_id,),
        )
    )


def _media_count(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM media WHERE project_id = ?", (project_id,)
        )[0]
    )


def test_complete_materializes_outputs_and_terminates_atomically(
    env, core_registry,
) -> None:
    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)

    out_a = _prepare_output(env, name="frame.svg", content=b"<svg/>")
    out_b = _prepare_output(
        env, name="story.md", content=b"# story",
        ordinal=1, is_primary=False, role="output", label="story",
    )
    completed = _complete(
        env,
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        outputs=[out_a, out_b],
    )

    # The task is terminal succeeded with the winning attempt recorded.
    assert completed.task.status == "succeeded"
    assert completed.task.winning_attempt_id == claim.attempt.id
    assert completed.task.finished_at == TS2
    # The attempt terminated succeeded with version advanced.
    assert completed.attempt.status == "succeeded"
    assert completed.attempt.status_version == started.status_version + 1
    assert completed.attempt.finished_at == TS2
    # Ordered outputs: exactly the two prepared media, primary first.
    assert [output.ordinal for output in completed.outputs] == [0, 1]
    assert completed.outputs[0].role == "result"
    assert completed.outputs[0].is_primary is True
    assert completed.outputs[1].is_primary is False

    # Ordered task_outputs rows with the byte identity and params evidence.
    rows = _task_output_rows(env.writer, task.id)
    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["is_primary"] == 1
    assert rows[0]["role"] == "result"
    assert rows[0]["media_id"] == completed.outputs[0].media_id
    params = json.loads(rows[0]["params_json"])
    assert params["content_hash"] == out_a["prepared"].digest
    assert params["label"] == "frame.svg"

    # Media state: two media rows, one managed location each, imported events.
    for output in completed.outputs:
        media = env.media_repo.show(env.writer, output.media_id)
        assert media.project_id == project.id
        assert media.content_hash == output.params["content_hash"]
        assert len(media.locations) == 1

    # One receipt covering every ordered event id (media events in ordinal
    # order, then the completed event), spanning the exact seq range.
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert len(completed.event_ids) == 3
    assert _project_head(env.writer, project.id) == head_before + 3
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_COMPLETED_EVENT_KIND
    # The receipt's ordered event ids match the events table order.
    with env.writer.read_only_connection() as conn:
        rows_events = conn.execute(
            "SELECT event_id FROM events WHERE project_id = ? "
            "ORDER BY project_seq ASC",
            (project.id,),
        ).fetchall()
    tail = [str(row[0]) for row in rows_events][-3:]
    assert completed.event_ids == tuple(tail)
    # The task stream verifies as a canonical hash chain.
    from astrid.core.events.service import EventAppendService

    verification = EventAppendService(core_registry).verify_stream(
        env.writer, stream_id
    )
    assert verification.event_count == verification.head_seq
    assert verification.head_hash is not None


def test_complete_replay_returns_stored_result_with_zero_new_rows(env) -> None:
    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    key = "t18-replay-k"

    first = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs, key=key,
    )
    before = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
        "outputs": len(_task_output_rows(env.writer, task.id)),
    }
    replayed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs, key=key,
    )
    assert replayed.to_dict() == first.to_dict()
    assert _receipt_count(env.writer, project.id) == before["receipts"]
    assert _project_head(env.writer, project.id) == before["head"]
    assert len(_task_output_rows(env.writer, task.id)) == before["outputs"]


def test_complete_mismatch_changes_nothing_before_mutation(env) -> None:
    from astrid.core.receipts import ReceiptMismatchError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    key = "t18-mismatch-k"
    _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs, key=key,
    )
    before = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
    }
    changed = [_prepare_output(env, name="changed.svg", content=b"<svg2/>")]
    with pytest.raises(ReceiptMismatchError):
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=changed, key=key,
        )
    assert _receipt_count(env.writer, project.id) == before["receipts"]
    assert _project_head(env.writer, project.id) == before["head"]


def test_complete_stale_or_losing_fences_write_nothing(env) -> None:
    from astrid.core.repositories.tasks import TaskTransitionError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    baseline = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
    }

    # Stale status version: typed outcome, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version + 7, outputs=outputs,
            key="t18-stale-version-k",
        )
    assert excinfo.value.reason == "stale_status_version"
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]

    # Wrong lease: typed outcome, zero rows.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id="not-the-lease",
            status_version=started.status_version, outputs=outputs,
            key="t18-lease-k",
        )
    assert excinfo.value.reason == "lease_mismatch"
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]

    # Foreign attempt (another task's attempt): typed outcome, zero rows.
    other_task, other_claim, _ = _started_attempt(
        env, project_id=project.id, idempotency_key="t18-foreign-claim-k"
    )
    foreign_baseline = _receipt_count(env.writer, project.id)
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=other_claim.attempt.id, lease_id=other_claim.attempt.lease_id,
            status_version=started.status_version, outputs=outputs,
            key="t18-foreign-k",
        )
    assert excinfo.value.reason == "attempt_task_mismatch"
    assert _receipt_count(env.writer, project.id) == foreign_baseline

    # Winning completion, then a losing completion on the same attempt:
    # the loser sees the terminal task and writes nothing.
    _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs,
        key="t18-winner-k",
    )
    after_win = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
    }
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=outputs,
            key="t18-loser-k",
        )
    assert excinfo.value.reason == "task_not_running"
    assert _receipt_count(env.writer, project.id) == after_win["receipts"]
    assert _project_head(env.writer, project.id) == after_win["head"]
    assert len(_task_output_rows(env.writer, task.id)) == 1


def test_complete_unblocks_eligible_dependents(env) -> None:
    project = _create_project(env)
    # Two tasks: `dep` hard-depends on both `task` and `fresh`; another
    # dependent `partial` hard-depends on `task` plus an unsatisfied task.
    task, claim, started = _started_attempt(env, project_id=project.id)
    fresh_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u, project_id=project.id,
            capability="rendering.timeline_visualize",
            spec=dict(SPEC_A), input_manifest=list(MANIFEST_A),
            idempotency_key="t18-fresh-admit-k", task_id=fresh_id,
            created_at=TS,
        )
    )
    never = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u, project_id=project.id,
            capability="rendering.timeline_visualize",
            spec=dict(SPEC_A), input_manifest=list(MANIFEST_A),
            idempotency_key="t18-never-admit-k", task_id=never,
            created_at=TS,
        )
    )
    dep_id = generate_lowercase_ulid()
    partial_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u, project_id=project.id,
            capability="rendering.timeline_visualize",
            spec=dict(SPEC_A), input_manifest=list(MANIFEST_A),
            idempotency_key="t18-dep-admit-k", task_id=dep_id,
            created_at=TS,
            dependencies=[
                {"task_id": task.id, "kind": "hard"},
                {"task_id": fresh_id, "kind": "hard"},
            ],
        )
    )
    UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u, project_id=project.id,
            capability="rendering.timeline_visualize",
            spec=dict(SPEC_A), input_manifest=list(MANIFEST_A),
            idempotency_key="t18-partial-admit-k", task_id=partial_id,
            created_at=TS,
            dependencies=[
                {"task_id": task.id, "kind": "hard"},
                {"task_id": never, "kind": "hard"},
            ],
        )
    )
    for task_id in (dep_id, partial_id):
        row = _task_row(env.writer, task_id)
        assert row["status"] == "blocked", task_id

    # Complete `task`: `dep` stays blocked (fresh unsatisfied), `partial`
    # stays blocked (never unsatisfied).
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]
    _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=outputs,
        key="t18-unblock-first-k",
    )
    assert _task_row(env.writer, dep_id)["status"] == "blocked"
    assert _task_row(env.writer, partial_id)["status"] == "blocked"

    # Complete `fresh`: `dep` now has every hard dep satisfied and unblocks.
    fresh_claim = _claim(env, project_id=project.id, idempotency_key="t18-fresh-claim-k")
    assert fresh_claim is not None and fresh_claim.task.id == fresh_id
    fresh_started = UnitOfWork(env.writer).run(
        lambda u: env.task_repo.start(
            u, project_id=project.id, task_id=fresh_id,
            attempt_id=fresh_claim.attempt.id,
            lease_id=fresh_claim.attempt.lease_id,
            expected_status_version=1,
            idempotency_key="t18-fresh-start-k", now=TS,
        )
    )
    completed = _complete(
        env, project_id=project.id, task_id=fresh_id,
        attempt_id=fresh_claim.attempt.id,
        lease_id=fresh_claim.attempt.lease_id,
        status_version=fresh_started.status_version, outputs=outputs,
        key="t18-unblock-second-k",
    )
    assert _task_row(env.writer, dep_id)["status"] == "queued"
    assert _task_row(env.writer, partial_id)["status"] == "blocked"
    # The completed event records the unblocked dependent deterministically.
    stream_id = f"{fresh_id}:core.task"
    events = _event_rows(env.writer, stream_id)
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["unblocked_dependents"] == [dep_id]


def test_complete_updates_parent_run_projection(env) -> None:
    from astrid.core.repositories.runs import RunRepository

    runs = RunRepository(events=env.task_repo._events, receipts=env.task_repo._receipts)
    project = _create_project(env)
    child_a = generate_lowercase_ulid()
    child_b = generate_lowercase_ulid()
    fan = UnitOfWork(env.writer).run(
        lambda u: runs.create(
            u, project_id=project.id,
            children=[
                {
                    "capability": "rendering.timeline_visualize",
                    "spec": dict(SPEC_A), "input_manifest": list(MANIFEST_A),
                    "task_id": child_a,
                },
                {
                    "capability": "rendering.timeline_visualize",
                    "spec": dict(SPEC_A), "input_manifest": list(MANIFEST_A),
                    "task_id": child_b,
                },
            ],
            idempotency_key="t18-run-k", created_at=TS,
        )
    )
    assert fan.run_id
    outputs = [_prepare_output(env, name="frame.svg", content=b"<svg/>")]

    def complete_child(child_id: str, key: str):
        claim = _claim(env, project_id=project.id, idempotency_key=key)
        assert claim is not None and claim.task.id == child_id
        started = UnitOfWork(env.writer).run(
            lambda u: env.task_repo.start(
                u, project_id=project.id, task_id=child_id,
                attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
                expected_status_version=1,
                idempotency_key=f"{key}:start", now=TS,
            )
        )
        return _complete(
            env, project_id=project.id, task_id=child_id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=outputs,
            key=f"{key}:complete",
        )

    # First child: the run stays running with derived progress.
    first = complete_child(child_a, "t18-run-claim-a")
    assert first.run is not None
    assert first.run["status"] == "running"
    assert first.run["succeeded"] == 1 and first.run["total_children"] == 2
    run_row = env.writer.submit(
        lambda session: session.query_one(
            "SELECT status, finished_at FROM runs WHERE id = ?", (fan.run_id,)
        )
    )
    assert run_row["status"] == "running"
    assert run_row["finished_at"] is None

    # Second child: every child terminal -> the run succeeds and stamps.
    second = complete_child(child_b, "t18-run-claim-b")
    assert second.run is not None
    assert second.run["status"] == "succeeded"
    assert second.run["succeeded"] == 2
    run_row = env.writer.submit(
        lambda session: session.query_one(
            "SELECT status, finished_at FROM runs WHERE id = ?", (fan.run_id,)
        )
    )
    assert run_row["status"] == "succeeded"
    assert run_row["finished_at"] == TS2


def test_complete_enforces_one_primary_and_unique_ordinals(env) -> None:
    from astrid.core.repositories.tasks import TaskValidationError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    baseline = _receipt_count(env.writer, project.id)

    # Duplicate ordinals are rejected before any mutation.
    dup = [
        _prepare_output(env, name="a.svg", content=b"<svg/>", ordinal=0),
        _prepare_output(
            env, name="b.svg", content=b"<svg2/>", ordinal=0,
            is_primary=False, role="output",
        ),
    ]
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=dup,
            key="t18-dup-ordinal-k",
        )
    assert "duplicated" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == baseline

    # Two primaries are rejected.
    two_primary = [
        _prepare_output(env, name="a.svg", content=b"<svg/>", ordinal=0),
        _prepare_output(env, name="b.svg", content=b"<svg2/>", ordinal=1),
    ]
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=two_primary,
            key="t18-two-primary-k",
        )
    assert "exactly one primary" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == baseline

    # A non-result primary is rejected (DDL CHECK mirror).
    bad_role = [
        _prepare_output(
            env, name="a.svg", content=b"<svg/>",
            ordinal=0, is_primary=True, role="output",
        )
    ]
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=bad_role,
            key="t18-bad-role-k",
        )
    assert "only a 'result' output may be primary" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == baseline
    assert _task_row(env.writer, task.id)["status"] == "running"


def test_complete_zero_outputs_with_result_succeeds_and_replays(env) -> None:
    from astrid.core.receipts import ReceiptMismatchError
    from astrid.core.repositories.tasks import TaskValidationError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    summary = {"headline": "42 scenes cut", "counts": {"scenes": 42}}

    # Zero outputs with no summary stays the current error: nothing written.
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=[],
            key="t18-empty-k",
        )
    assert (
        "at least one materialized output or a non-empty result"
        in str(excinfo.value)
    )
    assert _task_row(env.writer, task.id)["status"] == "running"
    assert _project_head(env.writer, project.id) == head_before

    # Zero outputs plus a non-empty result summary completes cleanly.
    completed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=[], result=summary,
        key="t18-result-only-k",
    )
    assert completed.task.status == "succeeded"
    assert completed.task.winning_attempt_id == claim.attempt.id
    assert completed.outputs == ()
    assert completed.result == summary
    assert _task_output_rows(env.writer, task.id) == []
    assert _media_count(env.writer, project.id) == 0
    assert len(completed.event_ids) == 1
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1

    # The summary rides in the completed event payload.
    stream_id = f"{task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_COMPLETED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data["result"] == summary
    assert data["outputs"] == []

    # An identical retry replays the stored result with zero new rows.
    replayed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version, outputs=[], result=summary,
        key="t18-result-only-k",
    )
    assert replayed.to_dict() == completed.to_dict()
    assert replayed.result == summary
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1

    # A changed summary under the same key mismatches before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=[],
            result={"headline": "different"}, key="t18-result-only-k",
        )
    assert _receipt_count(env.writer, project.id) == receipts_before + 1


def test_complete_evidence_only_primary_persists_null_media_id_facts(
    env,
) -> None:
    from astrid.core.repositories.tasks import TaskValidationError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    digest = "sha256:" + "a" * 64

    primary = _evidence_output()
    secondary = _evidence_output(
        ordinal=1, is_primary=False, role="evidence",
        path="notes.txt", digest=None, byte_size=None, label="notes",
    )
    completed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        outputs=[primary, secondary], key="t18-evidence-k",
    )
    assert completed.task.status == "succeeded"
    assert completed.task.winning_attempt_id == claim.attempt.id

    # Evidence persists outside media/task_outputs (media_id stays NOT
    # NULL): no rows there, one receipt, one completed event.
    assert _task_output_rows(env.writer, task.id) == []
    assert _media_count(env.writer, project.id) == 0
    assert len(completed.event_ids) == 1
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + 1

    # Read model: NULL media_id, declared facts in params, ordinal order.
    assert [output.ordinal for output in completed.outputs] == [0, 1]
    assert completed.outputs[0].media_id is None
    assert completed.outputs[0].role == "result"
    assert completed.outputs[0].is_primary is True
    assert completed.outputs[0].params == {
        "path": "report.json", "digest": digest,
        "byte_size": 128, "label": "report",
    }
    assert completed.outputs[1].media_id is None
    assert completed.outputs[1].role == "evidence"
    assert completed.outputs[1].params == {
        "path": "notes.txt", "label": "notes",
    }

    # The event payload mirrors the evidence facts with a null media_id.
    events = _event_rows(env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    data = json.loads(events[-1]["payload_json"])["data"]
    assert [item["ordinal"] for item in data["outputs"]] == [0, 1]
    assert data["outputs"][0]["media_id"] is None
    assert data["outputs"][0]["digest"] == digest
    assert data["outputs"][0]["byte_size"] == 128
    assert data["outputs"][1]["role"] == "evidence"

    # An evidence primary must keep role 'result' (DDL CHECK mirror).
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version,
            outputs=[_evidence_output(role="output")],
            key="t18-evidence-bad-role-k",
        )
    assert "only a 'result' output may be primary" in str(excinfo.value)

    # An evidence entry must not declare media materialization keys.
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version,
            outputs=[
                _evidence_output(media_id=generate_lowercase_ulid()),
            ],
            key="t18-evidence-media-key-k",
        )
    assert "must not declare media materialization keys" in str(excinfo.value)


def test_complete_mixed_media_and_evidence_ordinals_unique(env) -> None:
    from astrid.core.repositories.tasks import TaskValidationError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)

    media_a = _prepare_output(env, name="frame.svg", content=b"<svg/>")
    media_b = _prepare_output(
        env, name="story.md", content=b"# story",
        ordinal=2, is_primary=False, role="output", label="story",
    )
    evidence = _evidence_output(
        ordinal=1, is_primary=False, role="evidence",
        path="cut_report.json", digest="sha256:" + "b" * 64,
        byte_size=7, label=None,
    )
    completed = _complete(
        env, project_id=project.id, task_id=task.id,
        attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
        status_version=started.status_version,
        outputs=[media_a, evidence, media_b], key="t18-mixed-k",
    )
    assert completed.task.status == "succeeded"

    # One global ordinal order across both kinds; only media entries occupy
    # task_outputs/media state.
    assert [output.ordinal for output in completed.outputs] == [0, 1, 2]
    assert completed.outputs[1].media_id is None
    assert completed.outputs[1].params["path"] == "cut_report.json"
    rows = _task_output_rows(env.writer, task.id)
    assert [row["ordinal"] for row in rows] == [0, 2]
    assert rows[0]["media_id"] == completed.outputs[0].media_id
    assert rows[1]["media_id"] == completed.outputs[2].media_id
    assert _media_count(env.writer, project.id) == 2

    # The event payload carries all three entries in ordinal order.
    events = _event_rows(env.writer, f"{task.id}:{CORE_TASK_STREAM_TYPE}")
    data = json.loads(events[-1]["payload_json"])["data"]
    assert [item["ordinal"] for item in data["outputs"]] == [0, 1, 2]
    assert data["outputs"][0]["content_hash"] == media_a["prepared"].digest
    assert data["outputs"][2]["media_id"] == completed.outputs[2].media_id
    assert data["outputs"][1]["media_id"] is None

    # An evidence ordinal duplicating a media ordinal is rejected.
    dup = [
        _prepare_output(env, name="frame2.svg", content=b"<svg2/>"),
        _evidence_output(ordinal=0, is_primary=False, role="evidence"),
    ]
    with pytest.raises(TaskValidationError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version, outputs=dup,
            key="t18-mixed-dup-k",
        )
    assert "duplicated" in str(excinfo.value)


def test_complete_evidence_or_result_stale_fence_writes_nothing(env) -> None:
    from astrid.core.repositories.tasks import TaskTransitionError

    project = _create_project(env)
    task, claim, started = _started_attempt(env, project_id=project.id)
    baseline = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
    }

    # Stale version with an evidence-only output set: typed outcome.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id=claim.attempt.lease_id,
            status_version=started.status_version + 5,
            outputs=[_evidence_output()],
            key="t18-evidence-stale-k",
        )
    assert excinfo.value.reason == "stale_status_version"

    # Wrong lease with a bare result summary: typed outcome.
    with pytest.raises(TaskTransitionError) as excinfo:
        _complete(
            env, project_id=project.id, task_id=task.id,
            attempt_id=claim.attempt.id, lease_id="not-the-lease",
            status_version=started.status_version, outputs=[],
            result={"headline": "nope"},
            key="t18-result-stale-k",
        )
    assert excinfo.value.reason == "lease_mismatch"

    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]
    assert _task_output_rows(env.writer, task.id) == []
    assert _media_count(env.writer, project.id) == 0


# ---------------------------------------------------------------------------
# T19: service-level completion (plan step 10)
# ---------------------------------------------------------------------------


def _execute_prepared(env, *, project_id, handler, **overrides):
    """Execute through the service and return (service, prepared)."""
    service = ExecutionService(
        projects_root=env.projects_root, task_repo=env.task_repo
    )
    task = _admit(env, project_id=project_id, max_attempts=2)
    claim = _claim(env, project_id=project_id)
    assert claim is not None and claim.task.id == task.id
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
    result = service.execute(UnitOfWork(env.writer), **args)
    assert result.outcome == "prepared"
    assert result.prepared is not None
    return service, result.prepared


def _service_complete(env, service, prepared, *, key="t19-complete-k", **overrides):
    args = {
        "prepared": prepared,
        "media_repo": env.media_repo,
        "idempotency_key": key,
        "now": TS2,
    }
    args.update(overrides)
    return service.complete(UnitOfWork(env.writer), **args)


def test_service_complete_materializes_prepared_outputs_and_terminates(
    env, core_registry,
) -> None:
    from astrid.core.task_executor.service import CompletionResult

    project = _create_project(env)
    service, prepared = _execute_prepared(
        env,
        project_id=project.id,
        handler=FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"}),
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    assert _media_count(env.writer, project.id) == 0

    result = _service_complete(env, service, prepared)
    assert isinstance(result, CompletionResult)
    assert result.outcome == "completed"
    completed = result.completed
    assert completed is not None

    # The task is terminal succeeded with the winning attempt recorded and
    # the attempt terminated succeeded with the version advanced.
    assert completed.task.status == "succeeded"
    assert completed.task.winning_attempt_id == prepared.attempt.id
    assert completed.task.finished_at == TS2
    assert completed.attempt.status == "succeeded"
    assert completed.attempt.status_version == prepared.attempt.status_version + 1
    assert completed.attempt.finished_at == TS2

    # The full ordered output set: primary first, ordered roles, byte
    # identity on the materialized media rows.
    assert [output.ordinal for output in completed.outputs] == [0, 1]
    assert completed.outputs[0].is_primary is True
    assert completed.outputs[0].role == "result"
    assert completed.outputs[1].is_primary is False
    assert completed.outputs[1].role == "output"
    rows = _task_output_rows(env.writer, prepared.task.id)
    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["is_primary"] == 1
    assert rows[0]["media_id"] == completed.outputs[0].media_id
    assert _media_count(env.writer, project.id) == 2

    # One receipt covering every ordered event id (media events in ordinal
    # order, then the completed event) and a verifiable stream chain.
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert len(completed.event_ids) == 3
    assert _project_head(env.writer, project.id) == head_before + 3
    stream_id = f"{prepared.task.id}:{CORE_TASK_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == CORE_TASK_COMPLETED_EVENT_KIND
    with env.writer.read_only_connection() as conn:
        rows_events = conn.execute(
            "SELECT event_id FROM events WHERE project_id = ? "
            "ORDER BY project_seq ASC",
            (project.id,),
        ).fetchall()
    tail = [str(row[0]) for row in rows_events][-3:]
    assert completed.event_ids == tuple(tail)
    verification = EventAppendService(core_registry).verify_stream(
        env.writer, stream_id
    )
    assert verification.event_count == verification.head_seq
    assert verification.head_hash is not None


def test_service_complete_replay_returns_full_stored_output_set(env) -> None:
    from astrid.core.task_executor.service import CompletionResult

    project = _create_project(env)
    service, prepared = _execute_prepared(
        env,
        project_id=project.id,
        handler=FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"}),
    )
    key = "t19-replay-k"

    first = _service_complete(env, service, prepared, key=key)
    assert first.outcome == "completed" and first.completed is not None
    before = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
        "outputs": len(_task_output_rows(env.writer, prepared.task.id)),
        "media": _media_count(env.writer, project.id),
    }

    # Identical retry under the same key: the full stored output set comes
    # back and zero new rows are written.
    replayed = _service_complete(env, service, prepared, key=key)
    assert isinstance(replayed, CompletionResult)
    assert replayed.outcome == "completed"
    assert replayed.completed is not None
    assert replayed.completed.to_dict() == first.completed.to_dict()
    assert len(replayed.completed.outputs) == 2
    assert [output.ordinal for output in replayed.completed.outputs] == [0, 1]
    assert _receipt_count(env.writer, project.id) == before["receipts"]
    assert _project_head(env.writer, project.id) == before["head"]
    assert len(_task_output_rows(env.writer, prepared.task.id)) == before["outputs"]
    assert _media_count(env.writer, project.id) == before["media"]


def test_service_complete_stale_surfaces_typed_outcome_without_materialization(
    env,
) -> None:
    from dataclasses import replace

    from astrid.core.task_executor.service import CompletionResult

    project = _create_project(env)
    service, prepared = _execute_prepared(
        env,
        project_id=project.id,
        handler=FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"}),
    )
    baseline = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
        "media": _media_count(env.writer, project.id),
        "outputs": len(_task_output_rows(env.writer, prepared.task.id)),
    }

    # Stale status version: the typed stale outcome, zero semantic rows.
    stale = replace(
        prepared,
        attempt=replace(
            prepared.attempt,
            status_version=prepared.attempt.status_version + 7,
        ),
    )
    result = _service_complete(env, service, stale, key="t19-stale-version-k")
    assert isinstance(result, CompletionResult)
    assert result.outcome == "stale"
    assert result.error is not None
    assert result.error["reason"] == "stale_status_version"
    assert result.error["task_id"] == prepared.task.id
    assert result.error["attempt_id"] == prepared.attempt.id
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]
    assert _media_count(env.writer, project.id) == baseline["media"]
    assert len(_task_output_rows(env.writer, prepared.task.id)) == baseline["outputs"]
    assert _task_row(env.writer, prepared.task.id)["status"] == "running"

    # Wrong lease: another stale outcome, zero semantic rows.
    wrong_lease = replace(
        prepared,
        attempt=replace(prepared.attempt, lease_id="not-the-lease"),
    )
    result = _service_complete(env, service, wrong_lease, key="t19-lease-k")
    assert result.outcome == "stale"
    assert result.error is not None
    assert result.error["reason"] == "lease_mismatch"
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]
    assert _media_count(env.writer, project.id) == baseline["media"]
    assert len(_task_output_rows(env.writer, prepared.task.id)) == baseline["outputs"]


def test_service_complete_losing_surfaces_typed_outcome_without_materialization(
    env,
) -> None:
    from astrid.core.task_executor.service import CompletionResult

    project = _create_project(env)
    service, prepared = _execute_prepared(
        env,
        project_id=project.id,
        handler=FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"}),
    )

    # The winning completion decides the single-winner race first.
    winner = _service_complete(env, service, prepared, key="t19-winner-k")
    assert winner.outcome == "completed"
    after_win = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
        "media": _media_count(env.writer, project.id),
        "outputs": len(_task_output_rows(env.writer, prepared.task.id)),
    }

    # A second completion on the same attempt loses: typed outcome, and the
    # losing call materializes nothing (media/rows/receipts/head unchanged).
    loser = _service_complete(env, service, prepared, key="t19-loser-k")
    assert isinstance(loser, CompletionResult)
    assert loser.outcome == "losing"
    assert loser.error is not None
    assert loser.error["reason"] == "task_not_running"
    assert loser.error["task_id"] == prepared.task.id
    assert loser.completed is None
    assert _receipt_count(env.writer, project.id) == after_win["receipts"]
    assert _project_head(env.writer, project.id) == after_win["head"]
    assert _media_count(env.writer, project.id) == after_win["media"]
    assert len(_task_output_rows(env.writer, prepared.task.id)) == after_win["outputs"]


def test_service_complete_enforces_one_primary_and_ordered_roles(env) -> None:
    from dataclasses import replace

    from astrid.core.task_executor.service import CompletionResult

    project = _create_project(env)
    service, prepared = _execute_prepared(
        env,
        project_id=project.id,
        handler=FakeHandler({"frame.svg": b"<svg/>", "story.md": b"# story"}),
    )
    baseline = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
    }

    # Two primaries: the service rejects before the command runs.
    first, second = prepared.outputs
    two_primary = replace(
        prepared, outputs=(first, replace(second, is_primary=True))
    )
    from astrid.core.task_executor.service import TaskExecutorError

    with pytest.raises(TaskExecutorError) as excinfo:
        _service_complete(env, service, two_primary, key="t19-two-primary-k")
    assert "exactly one primary" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]

    # A non-result primary: rejected (DDL CHECK mirror).
    bad_role = replace(prepared, outputs=(replace(first, role="output"), second))
    with pytest.raises(TaskExecutorError) as excinfo:
        _service_complete(env, service, bad_role, key="t19-bad-role-k")
    assert "only a 'result' output may be primary" in str(excinfo.value)
    assert _receipt_count(env.writer, project.id) == baseline["receipts"]
    assert _project_head(env.writer, project.id) == baseline["head"]
    assert _task_row(env.writer, prepared.task.id)["status"] == "running"

    # Out-of-ordinal prepared outputs still complete with ordered roles: the
    # service sorts by ordinal before the command, so the stored output set
    # is deterministic regardless of the prepared tuple order.
    shuffled = replace(prepared, outputs=(second, first))
    result = _service_complete(env, service, shuffled, key="t19-ordered-k")
    assert isinstance(result, CompletionResult)
    assert result.outcome == "completed"
    assert result.completed is not None
    assert [output.ordinal for output in result.completed.outputs] == [0, 1]
    rows = _task_output_rows(env.writer, prepared.task.id)
    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["is_primary"] == 1 and rows[0]["role"] == "result"
    assert rows[1]["is_primary"] == 0 and rows[1]["role"] == "output"
