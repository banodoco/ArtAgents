"""Synchronous understanding repository adapter tests (m3 plan step 5, T6).

This suite proves the understanding adapter contract over the kernel
run/evidence verticals:

- the injected provider (the existing ``complete_json`` LLM client
  pattern) is invoked **outside** any SQLite transaction, and a provider
  failure (or a payload that fails normalization) leaves **zero** rows;
- the provider's reasoning / progress / final observations normalize into
  ordered evidence entries (``observation`` / ``measurement`` /
  ``decision``) plus one exact media-scoped observation per input/output
  media id, committed with **one zero-task run** (``children=[]``) in a
  single ``BEGIN IMMEDIATE`` unit of work;
- the public result carries only ``run_id``, ordered ``evidence_ids``, and
  the exact ``input_media_ids`` / ``output_media_ids`` — no task, attempt,
  or output identity is ever exposed or created (SC6);
- exact-media accounting is enforced: the payload's ``input_media_ids``
  must equal the request's exactly, every declared media id is validated
  same-project by the kernel evidence vertical (missing/foreign media roll
  the whole run back to zero rows), and a payload carrying a ``task_id``
  is rejected before mutation;
- identical replay under the same idempotency key returns the stored
  result with zero new rows, and a changed request under the same key is a
  mismatch before any mutation.

Every command runs through the adapter's one unit of work on the injected
kernel writer; reads run transaction-free on the writer.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import MediaRepository, ProjectRepository
from astrid.core.repositories.evidence import (
    CORE_EVIDENCE_RECORDED_EVENT_KIND,
    EvidenceRepository,
    EvidenceValidationError,
)
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.repositories.runs import (
    CORE_RUN_STREAM_TYPE,
    RunRepository,
)
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.understanding.executors.understand.repository_adapter import (
    UNDERSTANDING_RUN_KIND,
    UnderstandingAdapterError,
    UnderstandingRepositoryAdapter,
    UnderstandingResult,
)

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class DeterministicProvider:
    """The injected LLM client pattern: ``complete_json`` returns a fixed
    payload and records every call for assertions."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[dict] = []

    def complete_json(self, *, model, system, messages, response_schema, max_tokens):
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": messages,
                "response_schema": response_schema,
                "max_tokens": max_tokens,
            }
        )
        # A fresh deep copy each call so the adapter can never mutate the
        # shared fixture payload.
        return json.loads(json.dumps(self._payload))


class FailingProvider:
    """A provider that always raises, for the no-mutation failure test."""

    def complete_json(self, *, model, system, messages, response_schema, max_tokens):
        raise RuntimeError("deterministic provider failure")


class TransactionProbeProvider:
    """Wraps a provider and proves the call happens outside SQLite."""

    def __init__(self, inner, writer: DatabaseWriter) -> None:
        self._inner = inner
        self._writer = writer

    def complete_json(self, *, model, system, messages, response_schema, max_tokens):
        # The adapter must invoke the provider before opening its unit of
        # work: while the provider runs, the writer must have no active
        # transaction at all.
        in_transaction = self._writer.submit(lambda session: session.in_transaction)
        assert in_transaction is False
        return self._inner.complete_json(
            model=model,
            system=system,
            messages=messages,
            response_schema=response_schema,
            max_tokens=max_tokens,
        )


@pytest.fixture
def env(tmp_path: Path, core_registry):
    """Fresh kernel writer plus project/media/task/run/evidence repositories."""
    writer = DatabaseWriter(tmp_path / "understanding.sqlite3", core_registry)
    events = EventAppendService(core_registry)
    receipts = ReceiptService()
    try:
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
            task_repo=TaskRepository(events=events, receipts=receipts),
            run_repo=RunRepository(events=events, receipts=receipts),
            evidence_repo=EvidenceRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _payload(
    *,
    input_media_ids=(),
    output_media_ids=(),
    reasoning=None,
    progress=None,
    final=None,
    task_id=None,
):
    payload = {
        "reasoning": reasoning
        or {
            "summary": "the frame shows a sunrise",
            "notes": ["sky gradient", "no people"],
        },
        "progress": progress
        or {"summary": "analysis complete", "completed_fraction": 1.0},
        "final": final
        or {
            "summary": "sunrise over a calm lake",
            "findings": ["golden hour", "reflection visible"],
        },
        "input_media_ids": list(input_media_ids),
        "output_media_ids": list(output_media_ids),
    }
    if task_id is not None:
        payload["task_id"] = task_id
    return payload


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


def _write_png(env, name: str, data: bytes = PNG_BYTES) -> Path:
    path = env.projects_root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _import_media(
    env,
    *,
    project_id: str,
    media_id: str | None = None,
    data: bytes | None = None,
    realm: str = EXTERNAL_LOCAL_REALM,
    idempotency_key: str = "import-k-1",
):
    if data is None:
        # Distinct default bytes per call so project-scoped byte dedupe
        # never collapses two imports into one media row.
        data = PNG_BYTES + generate_lowercase_ulid().encode("ascii")
    path = _write_png(env, f"media-{generate_lowercase_ulid()}.png", data)
    prepared = prepare_media_file(path)
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": idempotency_key,
        "media_id": media_id or generate_lowercase_ulid(),
        "realm": realm,
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(u, **args)
    )


def _adapter(env, provider, **overrides):
    args = {"model": "test-model", "max_tokens": 64}
    args.update(overrides)
    return UnderstandingRepositoryAdapter(
        writer=env.writer,
        runs=env.run_repo,
        provider=provider,
        **args,
    )


def _counts(writer: DatabaseWriter) -> tuple[int, ...]:
    """(projects, event_streams, events, command_receipts, runs, tasks,
    execution_attempts, task_outputs, evidence_items)."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one("SELECT count(*) FROM runs")[0],
            session.query_one("SELECT count(*) FROM tasks")[0],
            session.query_one("SELECT count(*) FROM execution_attempts")[0],
            session.query_one("SELECT count(*) FROM task_outputs")[0],
            session.query_one("SELECT count(*) FROM evidence_items")[0],
        )
    )


def _evidence_rows(writer: DatabaseWriter):
    # rowid is SQLite insertion order — the submission order of the
    # evidence entries inside the run-create transaction (ULID lexicographic
    # order is not guaranteed within one millisecond).
    return writer.submit(
        lambda session: session.query(
            "SELECT id, run_id, task_id, kind, summary, media_id "
            "FROM evidence_items ORDER BY rowid"
        )
    )


def _event_kinds(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: [
            row["kind"]
            for row in session.query(
                "SELECT kind FROM events WHERE stream_id = ? ORDER BY seq ASC",
                (stream_id,),
            )
        ]
    )


def _receipt_row(writer: DatabaseWriter, project_id: str, key: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts WHERE project_id = ? "
            "AND idempotency_key = ?",
            (project_id, key),
        )
    )


# ---------------------------------------------------------------------------
# Happy path: one zero-task run + ordered evidence, exact media linkage
# ---------------------------------------------------------------------------


def test_understand_commits_zero_task_run_with_ordered_evidence(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-u1")
    output_media = _import_media(
        env, project_id=project.id, idempotency_key="import-u2"
    )
    provider = DeterministicProvider(
        _payload(
            input_media_ids=(input_media.id,),
            output_media_ids=(output_media.id,),
        )
    )
    adapter = _adapter(env, provider)
    counts = _counts(env.writer)

    result = adapter.understand(
        project_id=project.id,
        query="describe the first frame",
        input_media_ids=(input_media.id,),
        idempotency_key="understand-u1",
        created_at=TS,
    )

    assert isinstance(result, UnderstandingResult)
    # Public result: run id, ordered evidence ids, exact media ids — and
    # nothing else (no task/attempt/output identity).
    assert result.to_dict().keys() == {
        "run_id",
        "evidence_ids",
        "input_media_ids",
        "output_media_ids",
    }
    assert result.input_media_ids == (input_media.id,)
    assert result.output_media_ids == (output_media.id,)
    # 3 narrative observations + 1 input media observation + 1 output media
    # observation, in that order.
    assert len(result.evidence_ids) == 5

    # One zero-task understanding run: no tasks, attempts, or outputs.
    run_row = env.writer.submit(
        lambda session: session.query_one(
            "SELECT id, project_id, kind, status, input_json FROM runs WHERE id = ?",
            (result.run_id,),
        )
    )
    assert run_row["kind"] == UNDERSTANDING_RUN_KIND
    assert run_row["status"] == "running"
    assert json.loads(run_row["input_json"]) == {
        "query": "describe the first frame",
        "input_media_ids": [input_media.id],
        "output_media_ids": [output_media.id],
    }
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,  # one run stream
        counts[2] + 6,  # core.run.created + 5 evidence recorded
        counts[3] + 6,  # one run receipt + 5 evidence receipts
        counts[4] + 1,  # one run row
        counts[5],  # zero tasks
        counts[6],  # zero execution attempts
        counts[7],  # zero task outputs
        counts[8] + 5,  # five evidence rows
    )

    # Run stream: created event then the recorded events in submission order.
    run_stream_id = f"{result.run_id}:{CORE_RUN_STREAM_TYPE}"
    assert _event_kinds(env.writer, run_stream_id) == [
        "core.run.created",
        *([CORE_EVIDENCE_RECORDED_EVENT_KIND] * 5),
    ]

    # The complete run receipt returns the ordered evidence ids.
    receipt = _receipt_row(env.writer, project.id, "understand-u1")
    assert receipt["command_kind"] == "core.run.create"
    assert json.loads(receipt["result_json"])["evidence_ids"] == list(
        result.evidence_ids
    )

    # Exact media linkage: the media-scoped evidence rows carry the exact
    # media ids and the narrative rows carry the normalized observations.
    rows = _evidence_rows(env.writer)
    assert [row["kind"] for row in rows] == [
        "observation",
        "measurement",
        "decision",
        "observation",
        "observation",
    ]
    assert [row["task_id"] for row in rows] == [None] * 5
    assert [row["media_id"] for row in rows] == [
        None,
        None,
        None,
        input_media.id,
        output_media.id,
    ]
    assert rows[0]["summary"] == "the frame shows a sunrise"
    assert rows[1]["summary"] == "analysis complete"
    assert rows[2]["summary"] == "sunrise over a calm lake"
    assert rows[3]["summary"] == f"input media {input_media.id}"
    assert rows[4]["summary"] == f"output media {output_media.id}"
    # The narrative data payloads are the exact provider observations.
    assert json.loads(
        env.writer.submit(
            lambda session: session.query_one(
                "SELECT data_json FROM evidence_items WHERE id = ?",
                (result.evidence_ids[0],),
            )[0]
        )
    ) == {
        "summary": "the frame shows a sunrise",
        "notes": ["sky gradient", "no people"],
    }


# ---------------------------------------------------------------------------
# Deterministic clients: same inputs -> same normalized evidence
# ---------------------------------------------------------------------------


def test_understand_deterministic_client_same_inputs_same_result(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-d1")
    payload = _payload(input_media_ids=(input_media.id,), output_media_ids=())
    provider = DeterministicProvider(payload)
    adapter = _adapter(env, provider)

    first = adapter.understand(
        project_id=project.id,
        query="what is in this image?",
        input_media_ids=(input_media.id,),
        idempotency_key="understand-d1",
        created_at=TS,
    )
    second = adapter.understand(
        project_id=project.id,
        query="what is in this image?",
        input_media_ids=(input_media.id,),
        idempotency_key="understand-d2",
        created_at=TS,
    )

    # Deterministic normalization: identical requests under different keys
    # produce identical evidence content (ids differ, content matches).
    assert first.run_id != second.run_id
    assert len(first.evidence_ids) == len(second.evidence_ids) == 4
    rows = _evidence_rows(env.writer)
    # Both runs carry the exact same input media observation summary and the
    # same narrative observation summaries (4 evidence rows per run).
    assert [row["summary"] for row in rows] == [
        "the frame shows a sunrise",
        "analysis complete",
        "sunrise over a calm lake",
        f"input media {input_media.id}",
        "the frame shows a sunrise",
        "analysis complete",
        "sunrise over a calm lake",
        f"input media {input_media.id}",
    ]
    assert len(provider.calls) == 2
    # The provider saw the query and the exact input media reference.
    messages = provider.calls[0]["messages"]
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert content[0] == {"type": "text", "text": "what is in this image?"}
    assert content[1] == {
        "type": "media",
        "media_id": input_media.id,
        "role": "input",
    }
    assert provider.calls[0]["model"] == "test-model"
    assert provider.calls[0]["max_tokens"] == 64
    assert provider.calls[0]["response_schema"]["required"] == [
        "reasoning",
        "progress",
        "final",
        "input_media_ids",
        "output_media_ids",
    ]


# ---------------------------------------------------------------------------
# Provider failure and payload-shape failures: zero rows before mutation
# ---------------------------------------------------------------------------


def test_understand_provider_failure_leaves_no_mutation(env) -> None:
    project = _create_project(env)
    counts = _counts(env.writer)
    adapter = _adapter(env, FailingProvider())

    with pytest.raises(UnderstandingAdapterError):
        adapter.understand(
            project_id=project.id,
            query="describe this",
            idempotency_key="understand-fail1",
            created_at=TS,
        )

    # The provider call precedes any unit of work: nothing changed.
    assert _counts(env.writer) == counts


def test_understand_payload_shape_failure_leaves_no_mutation(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-p1")

    # A payload missing the final observation fails normalization before the
    # commit transaction opens.
    broken = _payload(input_media_ids=(input_media.id,), output_media_ids=())
    del broken["final"]
    counts = _counts(env.writer)
    with pytest.raises(UnderstandingAdapterError):
        _adapter(env, DeterministicProvider(broken)).understand(
            project_id=project.id,
            query="describe this",
            input_media_ids=(input_media.id,),
            idempotency_key="understand-p1",
            created_at=TS,
        )
    assert _counts(env.writer) == counts

    # A payload whose input media accounting is not exact is rejected before
    # any mutation too.
    mismatched = _payload(input_media_ids=(), output_media_ids=())
    with pytest.raises(UnderstandingAdapterError):
        _adapter(env, DeterministicProvider(mismatched)).understand(
            project_id=project.id,
            query="describe this",
            input_media_ids=(input_media.id,),
            idempotency_key="understand-p2",
            created_at=TS,
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# Provider invocation happens outside SQLite transactions
# ---------------------------------------------------------------------------


def test_understand_provider_call_outside_sqlite_transaction(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-t1")
    provider = DeterministicProvider(
        _payload(input_media_ids=(input_media.id,), output_media_ids=())
    )
    adapter = _adapter(env, TransactionProbeProvider(provider, env.writer))

    result = adapter.understand(
        project_id=project.id,
        query="describe this",
        input_media_ids=(input_media.id,),
        idempotency_key="understand-t1",
        created_at=TS,
    )
    assert result.run_id
    # The probe raised on any active transaction during the provider call.
    assert len(provider.calls) == 1


# ---------------------------------------------------------------------------
# Exact-media linkage: kernel same-project validation rolls back the run
# ---------------------------------------------------------------------------


def test_understand_exact_media_linkage_and_foreign_media_rollback(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    input_a = _import_media(
        env, project_id=project_a.id, idempotency_key="import-x1"
    )
    input_b = _import_media(
        env, project_id=project_a.id, idempotency_key="import-x2"
    )
    output_a = _import_media(
        env, project_id=project_a.id, idempotency_key="import-x3"
    )
    foreign = _import_media(
        env, project_id=project_b.id, idempotency_key="import-x4"
    )

    # Multiple exact input/output media ids all link to their own evidence
    # rows, in order.
    provider = DeterministicProvider(
        _payload(
            input_media_ids=(input_a.id, input_b.id),
            output_media_ids=(output_a.id,),
        )
    )
    adapter = _adapter(env, provider)
    result = adapter.understand(
        project_id=project_a.id,
        query="compare both frames",
        input_media_ids=(input_a.id, input_b.id),
        idempotency_key="understand-x1",
        created_at=TS,
    )
    assert result.input_media_ids == (input_a.id, input_b.id)
    assert result.output_media_ids == (output_a.id,)
    assert len(result.evidence_ids) == 6  # 3 narrative + 2 inputs + 1 output
    rows = _evidence_rows(env.writer)
    assert [row["media_id"] for row in rows] == [
        None,
        None,
        None,
        input_a.id,
        input_b.id,
        output_a.id,
    ]
    assert [row["summary"] for row in rows[3:]] == [
        f"input media {input_a.id}",
        f"input media {input_b.id}",
        f"output media {output_a.id}",
    ]

    # A foreign output media id: the kernel evidence vertical rejects it
    # inside the commit transaction and the whole run rolls back to zero
    # rows.
    counts = _counts(env.writer)
    with pytest.raises(EvidenceValidationError) as excinfo:
        _adapter(
            env,
            DeterministicProvider(
                _payload(
                    input_media_ids=(input_a.id,),
                    output_media_ids=(foreign.id,),
                )
            ),
        ).understand(
            project_id=project_a.id,
            query="describe this",
            input_media_ids=(input_a.id,),
            idempotency_key="understand-x2",
            created_at=TS,
        )
    assert excinfo.value.detail == "foreign_media"
    assert _counts(env.writer) == counts

    # A missing media id (row never imported) fails the same way.
    missing_id = generate_lowercase_ulid()
    with pytest.raises(EvidenceValidationError) as excinfo:
        _adapter(
            env,
            DeterministicProvider(
                _payload(
                    input_media_ids=(input_a.id,),
                    output_media_ids=(missing_id,),
                )
            ),
        ).understand(
            project_id=project_a.id,
            query="describe this",
            input_media_ids=(input_a.id,),
            idempotency_key="understand-x3",
            created_at=TS,
        )
    assert excinfo.value.detail == "missing_media"
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# Identical replay and mismatch under the same idempotency key
# ---------------------------------------------------------------------------


def test_understand_identical_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-r1")
    provider = DeterministicProvider(
        _payload(input_media_ids=(input_media.id,), output_media_ids=())
    )
    adapter = _adapter(env, provider)
    counts = _counts(env.writer)

    args = {
        "project_id": project.id,
        "query": "describe this",
        "input_media_ids": (input_media.id,),
        "idempotency_key": "understand-r1",
        "created_at": TS,
    }
    first = adapter.understand(**args)
    # Identical retry under the same key: the provider is deterministic, and
    # the kernel receipt gate returns the stored result with zero new rows.
    second = adapter.understand(**args)
    assert second == first
    assert second.run_id == first.run_id
    assert second.evidence_ids == first.evidence_ids
    assert second.input_media_ids == first.input_media_ids
    assert second.output_media_ids == first.output_media_ids
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 5,
        counts[3] + 5,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
        counts[8] + 4,
    )

    # A changed query under the same key is a mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        adapter.understand(**{**args, "query": "describe something else"})
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 5,
        counts[3] + 5,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
        counts[8] + 4,
    )


# ---------------------------------------------------------------------------
# Task identity exclusion: never exposed, never created
# ---------------------------------------------------------------------------


def test_understand_task_id_exclusion_before_mutation(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-s1")
    # A provider payload that tries to smuggle a task identity into the
    # response shape is rejected before any mutation.
    sneaky = _payload(
        input_media_ids=(input_media.id,),
        output_media_ids=(),
        task_id=generate_lowercase_ulid(),
    )
    counts = _counts(env.writer)
    with pytest.raises(UnderstandingAdapterError):
        _adapter(env, DeterministicProvider(sneaky)).understand(
            project_id=project.id,
            query="describe this",
            input_media_ids=(input_media.id,),
            idempotency_key="understand-s1",
            created_at=TS,
        )
    assert _counts(env.writer) == counts


def test_understand_result_and_rows_contain_no_task_identity(env) -> None:
    project = _create_project(env)
    input_media = _import_media(env, project_id=project.id, idempotency_key="import-s2")
    result = _adapter(
        env,
        DeterministicProvider(
            _payload(input_media_ids=(input_media.id,), output_media_ids=())
        ),
    ).understand(
        project_id=project.id,
        query="describe this",
        input_media_ids=(input_media.id,),
        idempotency_key="understand-s2",
        created_at=TS,
    )

    # The public result shape has no task, attempt, or output identity.
    assert "task_id" not in result.to_dict()
    assert "task_ids" not in result.to_dict()
    assert "attempt" not in result.to_dict()
    assert "outputs" not in result.to_dict()

    # No tasks, execution attempts, or task outputs rows were created, and
    # every evidence row has a NULL task_id (run-level evidence only).
    counts = _counts(env.writer)
    assert counts[5] == 0  # tasks
    assert counts[6] == 0  # execution_attempts
    assert counts[7] == 0  # task_outputs
    assert all(row["task_id"] is None for row in _evidence_rows(env.writer))
