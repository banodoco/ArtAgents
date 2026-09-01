"""Real generate_image round trip through the kernel executor (T7).

Plan step 6 proves the second real capability crossing the pack boundary:
a pack-owned adapter around ``generate_image.run_sdk`` is injected into the
kernel handler protocol and driven through the full m3 journey — admit,
claim, start, execute, complete — landing concrete PNG files and the pack's
generation manifest as managed media with ordered outputs, one winning
attempt, task and media events, one complete receipt, exact replay, and
byte-hash identity.

The journey is fully local and deterministic: the **actual** generation
pipeline (``generate_core`` → backend dispatch → sequential N=1 loop → PNG
metadata embedding → on-disk manifest) executes end to end with an injected
deterministic backend and a frozen clock, so identical specs produce
identical bytes. There is no provider key, network, GPU, remote execution,
or subprocess, and the kernel never imports the pack (or the adapter).
"""

from __future__ import annotations

import datetime as _datetime
import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from astrid.core.events.service import EventAppendService
from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.generation.backends.registry import (
    GenerationBackendDescriptor,
    GenerationBackendRegistry,
)
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
    CORE_TASK_STREAM_TYPE,
    TaskRepository,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.task_executor import ExecutionService

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

GENERATION_SPEC = {
    "model": "z-image",
    "mode": "t2i",
    "execution": "local",
    "prompt": "a serene mountain lake at dawn",
    "count": 2,
    "seed": 42,
}

# ---------------------------------------------------------------------------
# Deterministic injected backends (the only generation authority in tests)
# ---------------------------------------------------------------------------


class DeterministicImageBackend(BackendAdapter):
    """A deterministic backend: same (prompt, seed) -> identical PNG bytes."""

    def generate(self, entry, mode, params, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        seed = int(params.get("seed", 0))
        prompt = str(params.get("prompt", ""))
        digest = hashlib.sha256(f"{prompt}:{seed}".encode("utf-8")).hexdigest()
        color = (
            int(digest[0:2], 16),
            int(digest[2:4], 16),
            int(digest[4:6], 16),
        )
        image = Image.new("RGB", (64, 64), color)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        path = out_dir / f"{seed}-{entry.id}.png"
        path.write_bytes(buffer.getvalue())
        return GenerationResult(
            image_paths=[path],
            seed_used=seed,
            model_actual=entry.id,
            duration_ms=1,
            applied_features=["prompt", "seed"],
        )


class FailingImageBackend(BackendAdapter):
    """A backend that always fails, for the fenced-failure journey."""

    def generate(self, entry, mode, params, out_dir):
        raise RuntimeError("deterministic backend failure")


class _FrozenDatetime(_datetime.datetime):
    """A datetime class whose ``now()`` always returns one fixed instant."""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 16, 0, 30, 0, tzinfo=tz or _datetime.timezone.utc)


def _deterministic_registry(backend_class: type[BackendAdapter]) -> GenerationBackendRegistry:
    """A registry whose ``local`` backend is the injected deterministic one."""
    registry = GenerationBackendRegistry(descriptors=())
    registry._descriptors.clear()  # noqa: SLF001 - test-only synthetic registry
    registry.register(
        GenerationBackendDescriptor(
            backend_id="local",
            module=__name__,
            class_name=backend_class.__name__,
            label="Deterministic (test)",
        )
    )
    return registry


def _install_generation_backend(
    monkeypatch: pytest.MonkeyPatch,
    backend_class: type[BackendAdapter],
) -> None:
    """Import the real run module in-band and inject the deterministic backend.

    The run module guards direct import, so the import happens inside the
    canonical runtime context (the same context the adapter uses), then
    ``load_default_generation_backend_registry`` is patched on the module
    and the module's clock is frozen so the PNG metadata embedding is
    byte-deterministic.
    """
    from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

    with canonical_runtime_entrypoint("generation.generate_image"):
        from astrid.packs.generation.executors.generate_image import run as run_mod

        monkeypatch.setattr(
            run_mod,
            "load_default_generation_backend_registry",
            lambda: _deterministic_registry(backend_class),
        )
        monkeypatch.setattr(run_mod, "datetime", _FrozenDatetime)


class TransactionProbeAdapter:
    """Wraps a handler and proves its work happens outside SQLite transactions."""

    def __init__(self, inner, writer: DatabaseWriter) -> None:
        self._inner = inner
        self._writer = writer

    def execute(self, *, task, staging_dir):
        # The kernel can only hold a transaction inside a UnitOfWork; while
        # the handler runs, the caller's writer must have no active
        # transaction at all (no pack opens its own).
        in_transaction = self._writer.submit(lambda session: session.in_transaction)
        assert in_transaction is False
        return self._inner.execute(task=task, staging_dir=staging_dir)


# ---------------------------------------------------------------------------
# Kernel journey helpers (mirror the renderer round-trip journey)
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, core_registry):
    """Fresh kernel writer plus project/task/media repositories over one root."""
    from types import SimpleNamespace

    from astrid.core.store.writer import DatabaseWriter

    db_path = tmp_path / "generation_env.sqlite3"
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


def _admit(env, *, project_id: str, task_id: str | None = None, **overrides):
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": "generation.generate_image",
        "spec": dict(GENERATION_SPEC),
        "input_manifest": [],
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
    """Admit/claim/start/execute through the service; return (task, service, prepared)."""
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
# The real generation journey
# ---------------------------------------------------------------------------


def test_real_generation_round_trip_completes_through_managed_media(
    env, core_registry, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    project = _create_project(env)
    adapter = GenerateImageAdapter(projects_root=env.projects_root)
    task, service, prepared = _execute_prepared(
        env, project_id=project.id, adapter=adapter
    )
    receipts_before = _receipt_count(env.writer, project.id)
    head_before = _project_head(env.writer, project.id)
    assert _media_count(env.writer, project.id) == 0

    # The real pipeline wrote concrete PNG files plus the pack's own
    # manifest under the assigned staging root, and every prepared output
    # is a byte-hashed media descriptor with the manifest as the single
    # primary result.
    assert prepared.attempt.status == "running"
    assert prepared.attempt.status_version == 2
    staging_files = {
        path.relative_to(prepared.staging_dir).as_posix()
        for path in prepared.staging_dir.rglob("*")
        if path.is_file()
    }
    assert "manifest.json" in staging_files
    png_files = sorted(name for name in staging_files if name.endswith(".png"))
    assert len(png_files) == 2
    assert all(name.startswith("images/") for name in png_files)
    assert len(prepared.outputs) == 3
    assert prepared.outputs[0].is_primary is True
    assert prepared.outputs[0].role == "result"
    assert prepared.outputs[0].path == "manifest.json"
    assert prepared.outputs[1].role == "output"

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

    # Ordered outputs: primary manifest first, deterministic ordinals,
    # concrete media.
    outputs = completed_model.outputs
    assert [output.ordinal for output in outputs] == list(range(len(outputs)))
    assert outputs[0].is_primary is True and outputs[0].role == "result"
    assert outputs[0].params["path"] == "manifest.json"
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

    # The task never resurrects and the winning attempt is unique.
    assert _task_row(env.writer, task.id)["status"] == "succeeded"
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "succeeded"


def test_real_generation_round_trip_replays_identical_stored_result(
    env, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    project = _create_project(env)
    adapter = GenerateImageAdapter(projects_root=env.projects_root)
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


def test_real_generation_round_trip_hash_identity_across_tasks(
    env, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    project = _create_project(env)
    adapter = GenerateImageAdapter(projects_root=env.projects_root)

    _, service_first, prepared_first = _execute_prepared(
        env,
        project_id=project.id,
        adapter=adapter,
        claim_key="claim-1",
        idempotency_key="execute-1",
    )
    first = _complete(env, service_first, prepared_first, key="hash-first-k")
    assert first.outcome == "completed" and first.completed is not None

    # A second task with the same immutable spec generates byte-identical
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


def test_generation_handler_failure_routes_through_fenced_failure(
    env, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, FailingImageBackend)
    project = _create_project(env)
    adapter = GenerateImageAdapter(projects_root=env.projects_root)
    task = _admit(env, project_id=project.id)
    claim = _claim(env, project_id=project.id)
    assert claim is not None and claim.task.id == task.id
    service = ExecutionService(
        projects_root=env.projects_root, task_repo=env.task_repo
    )
    result = service.execute(
        UnitOfWork(env.writer),
        project_id=project.id,
        task_id=claim.task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=claim.attempt.status_version,
        idempotency_key="execute-fail-k",
        handler=adapter,
        now=TS2,
    )

    # The handler exception was routed through the fenced failure command:
    # the task and attempt are terminal failed, no media or outputs were
    # materialized, and no completion ever happens.
    assert result.outcome == "failed"
    assert result.failure is not None
    assert result.failure.task.status == "failed"
    assert result.failure.attempt.status == "failed"
    assert result.error is not None and result.error["reason"] == "handler_failed"
    assert _task_row(env.writer, task.id)["status"] == "failed"
    attempts = _attempt_rows(env.writer, task.id)
    assert len(attempts) == 1 and attempts[0]["status"] == "failed"
    assert _media_count(env.writer, project.id) == 0
    assert len(_task_output_rows(env.writer, task.id)) == 0


def test_generation_handler_runs_outside_sqlite_transactions(
    env, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    project = _create_project(env)
    inner = GenerateImageAdapter(projects_root=env.projects_root)
    adapter = TransactionProbeAdapter(inner, env.writer)
    _, _, prepared = _execute_prepared(
        env, project_id=project.id, adapter=adapter
    )

    # The probe ran inside the handler (between the kernel's two short
    # UoW submissions) and proved no transaction was open, so handler work
    # happens outside SQLite. The concrete outputs still landed only under
    # the assigned staging directory.
    staging_files = {
        path.relative_to(prepared.staging_dir).as_posix()
        for path in prepared.staging_dir.rglob("*")
        if path.is_file()
    }
    assert "manifest.json" in staging_files
    assert any(name.endswith(".png") for name in staging_files)
    for name in staging_files:
        assert ".." not in name and not Path(name).is_absolute()


def test_generation_adapter_is_pack_owned_and_confines_outputs(env) -> None:
    """No kernel import of the pack, no provider/remote path, staging-only writes."""
    import astrid.core.repositories.tasks as tasks_module
    import astrid.core.task_executor.service as service_module
    from astrid.packs.generation.executors.generate_image import task_adapter

    adapter_source = Path(task_adapter.__file__).read_text(encoding="utf-8")
    kernel_sources = (
        Path(service_module.__file__).read_text(encoding="utf-8")
        + Path(tasks_module.__file__).read_text(encoding="utf-8")
    )

    # The adapter is pack code: it never imports the kernel executor.
    assert "import astrid.core.task_executor" not in adapter_source
    assert "from astrid.core.task_executor" not in adapter_source
    for forbidden in (
        "urllib",
        "requests",
        "socket",
        "openai",
        "anthropic",
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


def test_shot_generation_recipe_round_trips_in_task_and_result_inputs(
    env, monkeypatch,
) -> None:
    from astrid.packs.generation.executors.generate_image.task_adapter import (
        GenerateImageAdapter,
    )

    _install_generation_backend(monkeypatch, DeterministicImageBackend)
    project = _create_project(env)
    recipe = {
        "schema": "astrid.shot-generation-recipe/v1",
        "project_id": project.id,
        "shot_id": "shot-02",
        "target_role": "primary_visual",
        "prompt_binding": {
            "id": "binding-02",
            "head": 3,
            "media_id": "prompt-media",
            "content_sha256": "a" * 64,
        },
        "generator": {
            "capability_id": "generation.generate_image",
            "model": "z-image",
            "backend": "local",
            "mode": "t2i",
            "settings": {"seed": 42},
        },
        "inputs": [],
        "parent_media_id": "parent-media",
        "parent_content_sha256": "b" * 64,
    }
    task = _admit(
        env,
        project_id=project.id,
        spec={**GENERATION_SPEC, "shot_generation_recipe": recipe},
    )
    claim = _claim(env, project_id=project.id)
    service = ExecutionService(projects_root=env.projects_root, task_repo=env.task_repo)
    prepared_result = service.execute(
        UnitOfWork(env.writer),
        project_id=project.id,
        task_id=task.id,
        attempt_id=claim.attempt.id,
        lease_id=claim.attempt.lease_id,
        expected_status_version=claim.attempt.status_version,
        idempotency_key="execute-recipe",
        handler=GenerateImageAdapter(projects_root=env.projects_root),
        now=TS2,
    )
    assert prepared_result.outcome == "prepared"
    prepared = prepared_result.prepared
    assert prepared is not None
    assert task.spec["shot_generation_recipe"] == recipe
    assert prepared.manifest.inputs["shot_generation_recipe"] == recipe
    completed = _complete(env, service, prepared)
    assert completed.outcome == "completed"
    assert completed.completed is not None
    assert completed.completed.outputs[0].params["path"] == "manifest.json"
