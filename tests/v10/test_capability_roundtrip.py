"""Real timeline_visualize round trip through the kernel executor (T23).

Plan step 14 proves the first real capability crossing the pack boundary:
a pack-owned adapter around ``timeline_visualize.run_sdk`` is injected into
the kernel handler protocol and driven through the full m2 journey —
admit, claim, start, execute, complete — landing concrete SVG/PNG/Markdown
files as managed media with ordered outputs, one winning attempt, task and
media events, one complete receipt, exact replay, and byte-hash identity.

The journey is fully local: the seeded timeline is a normalized re-chained
copy of the existing ``desert_slice`` fixture (the source fixture stays
read-only), the renderer runs in-process with no provider key, network,
GPU, remote execution, or subprocess, and the kernel never imports the pack
(or the adapter).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORTED_EVENT_KIND,
    CORE_MEDIA_STREAM_TYPE,
    MANAGED_LOCAL_REALM,
    MediaRepository,
)
from astrid.core.repositories.tasks import (
    CORE_TASK_COMPLETED_EVENT_KIND,
    CORE_TASK_STARTED_EVENT_KIND,
    CORE_TASK_STREAM_TYPE,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.task_executor import ExecutionService
from astrid.core.timeline.events.schema.serialize import TimelineEvent, with_event_hash

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

TESTS_ROOT = Path(__file__).resolve().parents[1]
DESERT_SLICE = TESTS_ROOT / "fixtures" / "timeline_visualize" / "desert_slice"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"

ADAPTER_SPEC = {
    "project_slug": "roundtrip",
    "timeline_ulid": TIMELINE_ULID,
    "layout": "time-scaled",
    "formats": ["png", "svg", "md"],
    "filmstrip": "off",
}


@pytest.fixture
def env(tmp_path, core_registry):
    """Fresh kernel writer plus project/task/media repositories over one root."""
    from types import SimpleNamespace

    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "capability_env.sqlite3"
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


# ---------------------------------------------------------------------------
# Seeding: the existing fixture, copied read-only and schema-0.0.2 compatible
# ---------------------------------------------------------------------------


def _strip_app(value):
    """Drop the Reigh editor 'app' metadata extension (newer than schema 0.0.2)."""
    if isinstance(value, dict):
        return {k: _strip_app(v) for k, v in value.items() if k != "app"}
    if isinstance(value, list):
        return [_strip_app(v) for v in value]
    return value


def _normalize_and_rechain(log_path: Path) -> None:
    """Strip editor extensions and recompute the self-contained hash chain.

    The fixture's event log is hash-chained: stripping ``app`` from the
    payload without re-chaining breaks integrity, so every modified event is
    re-hashed in order (``with_event_hash``) and the stored ``hash`` fields
    are rewritten. The captured tail is authoritative; the head sidecar
    mismatch is diagnostic only.
    """
    lines = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    rechained: list[dict] = []
    previous_hash: str | None = None
    for line in lines:
        raw = dict(line)
        payload = raw.get("payload")
        if isinstance(payload, dict):
            raw["payload"] = _strip_app(payload)
        event = with_event_hash(TimelineEvent.from_dict(raw), prev_hash=previous_hash)
        previous_hash = event.hash
        rechained.append(event.to_json_obj())
    log_path.write_text(
        "\n".join(
            json.dumps(item, sort_keys=True, separators=(",", ":"))
            for item in rechained
        )
        + "\n",
        encoding="utf-8",
    )


def _seed_timeline(projects_root: Path, slug: str) -> Path:
    """Copy the fixture read-only into a managed project and return the dir."""
    from astrid.core.foundation.project_paths import project_dir
    from astrid.core.project.project import create_project

    create_project(slug, root=projects_root)
    proot = project_dir(slug, root=projects_root)
    timeline_dir = proot / "timelines" / TIMELINE_ULID
    shutil.copytree(DESERT_SLICE, timeline_dir)
    _normalize_and_rechain(timeline_dir / "assembly.jsonl")
    return timeline_dir


# ---------------------------------------------------------------------------
# Kernel journey helpers
# ---------------------------------------------------------------------------


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


def _admit(env, *, project_id: str, task_id: str | None = None, **overrides):
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": "rendering.timeline_visualize",
        "spec": dict(ADAPTER_SPEC),
        "input_manifest": [TIMELINE_ULID],
        "idempotency_key": f"admit-{task_id}-k",
        "task_id": task_id,
        "max_attempts": 1,
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


def _task_row(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    )


def _attempt_rows(writer: DatabaseWriter, task_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM execution_attempts WHERE task_id = ? ORDER BY attempt_no ASC",
            (task_id,),
        )
    )


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC", (stream_id,)
        )
    )


def _receipt_count(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) FROM command_receipts WHERE project_id = ?", (project_id,)
        )[0]
    )


def _project_head(writer: DatabaseWriter, project_id: str) -> int:
    return writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )[0]
    )


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


def _verify_chain(env, core_registry, task_id: str):
    stream_id = f"{task_id}:{CORE_TASK_STREAM_TYPE}"
    verification = EventAppendService(core_registry).verify_stream(
        env.writer, stream_id
    )
    assert verification.event_count == verification.head_seq
    assert verification.head_hash is not None
    return stream_id


def _execute_prepared(
    env, *, project_id, adapter, claim_key: str = "claim-k", **overrides
):
    """Admit/claim/start/execute through the service; return (service, prepared)."""
    task = _admit(env, project_id=project_id)
    claim = _claim(env, project_id=project_id, idempotency_key=claim_key)
    assert claim is not None and claim.task.id == task.id
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
        "handler": adapter,
        "now": TS2,
    }
    args.update(overrides)
    result = service.execute(UnitOfWork(env.writer), **args)
    assert result.outcome == "prepared"
    assert result.prepared is not None
    return task, service, result.prepared


def _complete(env, service, prepared, *, key="complete-k", **overrides):
    args = {
        "prepared": prepared,
        "media_repo": env.media_repo,
        "idempotency_key": key,
        "now": TS2,
    }
    args.update(overrides)
    return service.complete(UnitOfWork(env.writer), **args)


# ---------------------------------------------------------------------------
# The real journey
# ---------------------------------------------------------------------------


def test_real_renderer_round_trip_completes_through_managed_media(
    env, core_registry,
) -> None:
    from astrid.packs.rendering.executors.timeline_visualize.task_adapter import (
        TimelineVisualizeAdapter,
    )

    fixture_digest_before = hashlib.sha256(
        (DESERT_SLICE / "assembly.jsonl").read_bytes()
    ).hexdigest()
    project = _create_project(env)
    _seed_timeline(env.projects_root, ADAPTER_SPEC["project_slug"])
    adapter = TimelineVisualizeAdapter(projects_root=env.projects_root)
    task, service, prepared = _execute_prepared(
        env, project_id=project.id, adapter=adapter
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    assert _media_count(env.writer, project.id) == 0

    # The handler wrote concrete SVG/PNG/Markdown files under the assigned
    # staging root (no directory identities), and every prepared output is a
    # byte-hashed media descriptor.
    assert prepared.attempt.status == "running"
    assert prepared.attempt.status_version == 2
    staging_files = {
        path.relative_to(prepared.staging_dir).as_posix()
        for path in prepared.staging_dir.rglob("*")
        if path.is_file()
    }
    assert any(name.endswith(".png") for name in staging_files)
    assert any(name.endswith(".svg") for name in staging_files)
    assert any(name.endswith(".md") for name in staging_files)
    assert "agent-view/manifest.json" in staging_files
    assert len(prepared.outputs) >= 5
    assert prepared.outputs[0].is_primary is True
    assert prepared.outputs[0].role == "result"
    assert prepared.outputs[0].path == "agent-view/manifest.json"

    completed = _complete(env, service, prepared)
    assert completed.outcome == "completed"
    completed_model = completed.completed
    assert completed_model is not None

    # The task is terminal succeeded with the one winning attempt.
    assert completed_model.task.status == "succeeded"
    assert completed_model.task.winning_attempt_id == prepared.attempt.id
    assert completed_model.task.finished_at == TS2
    assert completed_model.attempt.status == "succeeded"
    assert completed_model.attempt.status_version == prepared.attempt.status_version + 1
    assert completed_model.attempt.finished_at == TS2

    # Ordered outputs: primary first, deterministic ordinals, concrete media.
    outputs = completed_model.outputs
    assert [output.ordinal for output in outputs] == list(range(len(outputs)))
    assert outputs[0].is_primary is True and outputs[0].role == "result"
    assert all(not output.is_primary or output.role == "result" for output in outputs)
    rows = _task_output_rows(env.writer, task.id)
    assert [row["ordinal"] for row in rows] == list(range(len(rows)))
    assert rows[0]["is_primary"] == 1 and rows[0]["role"] == "result"
    assert _media_count(env.writer, project.id) == len(outputs)

    # Managed media: byte identity, managed local locations, concrete bytes.
    for output in outputs:
        media = env.media_repo.show(env.writer, output.media_id)
        assert media.project_id == project.id
        assert media.content_hash == output.params["content_hash"]
        assert len(media.locations) == 1
        assert media.locations[0].realm == MANAGED_LOCAL_REALM
        digest = media.content_hash
        managed_path = (
            env.projects_root
            / ".astrid"
            / "media"
            / "sha256"
            / digest[:2]
            / digest[2:4]
            / digest
        )
        assert managed_path.is_file()
        assert hashlib.sha256(managed_path.read_bytes()).hexdigest() == digest

    # Events: one media imported event per output, then the completed event,
    # one receipt covering every ordered event id, and a verifiable chain.
    assert _receipt_count(env.writer, project.id) == receipts_before + 1
    assert _project_head(env.writer, project.id) == head_before + len(outputs) + 1
    stream_id = _verify_chain(env, core_registry, task.id)
    events = _event_rows(env.writer, stream_id)
    assert [str(row["kind"]) for row in events][-1] == CORE_TASK_COMPLETED_EVENT_KIND
    assert len(completed_model.event_ids) == len(outputs) + 1
    with env.writer.read_only_connection() as conn:
        rows_events = conn.execute(
            "SELECT event_id FROM events WHERE project_id = ? ORDER BY project_seq ASC",
            (project.id,),
        ).fetchall()
    tail = [str(row[0]) for row in rows_events][-(len(outputs) + 1):]
    assert completed_model.event_ids == tuple(tail)
    for output in outputs:
        media_stream = f"{output.media_id}:{CORE_MEDIA_STREAM_TYPE}"
        media_events = _event_rows(env.writer, media_stream)
        assert media_events[-1]["kind"] == CORE_MEDIA_IMPORTED_EVENT_KIND

    # The source fixture stayed read-only (bytes unchanged) and the task
    # never resurrects.
    assert hashlib.sha256(
        (DESERT_SLICE / "assembly.jsonl").read_bytes()
    ).hexdigest() == fixture_digest_before
    assert _task_row(env.writer, task.id)["status"] == "succeeded"
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "succeeded"


def test_real_renderer_round_trip_replays_identical_stored_result(
    env,
) -> None:
    from astrid.packs.rendering.executors.timeline_visualize.task_adapter import (
        TimelineVisualizeAdapter,
    )

    project = _create_project(env)
    _seed_timeline(env.projects_root, ADAPTER_SPEC["project_slug"])
    adapter = TimelineVisualizeAdapter(projects_root=env.projects_root)
    _, service, prepared = _execute_prepared(
        env, project_id=project.id, adapter=adapter
    )
    key = "roundtrip-replay-k"

    first = _complete(env, service, prepared, key=key)
    assert first.outcome == "completed" and first.completed is not None
    before = {
        "receipts": _receipt_count(env.writer, project.id),
        "head": _project_head(env.writer, project.id),
        "outputs": len(_task_output_rows(env.writer, prepared.task.id)),
        "media": _media_count(env.writer, project.id),
    }

    replayed = _complete(env, service, prepared, key=key)
    assert replayed.outcome == "completed"
    assert replayed.completed is not None
    assert replayed.completed.to_dict() == first.completed.to_dict()
    assert len(replayed.completed.outputs) == before["outputs"]
    assert _receipt_count(env.writer, project.id) == before["receipts"]
    assert _project_head(env.writer, project.id) == before["head"]
    assert len(_task_output_rows(env.writer, prepared.task.id)) == before["outputs"]
    assert _media_count(env.writer, project.id) == before["media"]


def test_real_renderer_round_trip_hash_identity_across_tasks(env) -> None:
    from astrid.packs.rendering.executors.timeline_visualize.task_adapter import (
        TimelineVisualizeAdapter,
    )

    project = _create_project(env)
    _seed_timeline(env.projects_root, ADAPTER_SPEC["project_slug"])
    adapter = TimelineVisualizeAdapter(projects_root=env.projects_root)

    _, service_first, prepared_first = _execute_prepared(
        env,
        project_id=project.id,
        adapter=adapter,
        claim_key="claim-1",
        idempotency_key="execute-1",
    )
    first = _complete(env, service_first, prepared_first, key="hash-first-k")
    assert first.outcome == "completed" and first.completed is not None

    # A second task with the same immutable spec renders byte-identical
    # outputs: media identity is byte SHA-256 alone (SD2).
    task_two, service_two, prepared_two = _execute_prepared(
        env,
        project_id=project.id,
        adapter=adapter,
        claim_key="claim-2",
        idempotency_key="execute-2",
    )
    assert task_two.id != prepared_first.task.id
    second = _complete(env, service_two, prepared_two, key="hash-second-k")
    assert second.outcome == "completed" and second.completed is not None

    first_by_path = {out.params["path"]: out for out in first.completed.outputs}
    second_by_path = {out.params["path"]: out for out in second.completed.outputs}
    assert set(first_by_path) == set(second_by_path)
    for path in first_by_path:
        first_out = first_by_path[path]
        second_out = second_by_path[path]
        assert first_out.ordinal == second_out.ordinal
        assert first_out.params["content_hash"] == second_out.params["content_hash"]
        # Byte identity is the media identity (SD2): the identical bytes
        # reuse the exact same media row and managed location.
        assert first_out.media_id == second_out.media_id
        assert (
            env.media_repo.show(env.writer, first_out.media_id).content_hash
            == env.media_repo.show(env.writer, second_out.media_id).content_hash
        )


def test_adapter_is_pack_owned_and_fully_local(env) -> None:
    """No provider key, network, GPU, remote execution, or kernel import."""
    import astrid.core.repositories.tasks as tasks_module
    import astrid.core.task_executor.service as service_module
    from astrid.packs.rendering.executors.timeline_visualize import task_adapter

    adapter_source = Path(task_adapter.__file__).read_text(encoding="utf-8")
    kernel_sources = (
        Path(service_module.__file__).read_text(encoding="utf-8")
        + Path(tasks_module.__file__).read_text(encoding="utf-8")
    )

    # The adapter is pack code: it never imports the kernel executor, and it
    # uses only local rendering (Pillow/SVG/Markdown) — no remote/provider
    # path, no subprocess, no GPU.
    assert "import astrid.core.task_executor" not in adapter_source
    assert "from astrid.core.task_executor" not in adapter_source
    for forbidden in (
        "urllib",
        "requests",
        "socket",
        "openai",
        "anthropic",
        "fal",
        "subprocess",
        "torch",
        "cuda",
    ):
        assert forbidden not in adapter_source, f"remote/provider path leaked: {forbidden}"

    # The kernel never imports packs or the adapter (single-writer,
    # kernel-to-pack prohibition).
    assert "astrid.packs" not in kernel_sources
    assert "task_adapter" not in kernel_sources
    assert "import astrid.core.execution" not in kernel_sources
