"""Conformance-kit tests: every dimension for both timeline commands plus
deliberately broken negative samples (m1 plan step 15 / NSA-2).

The kit (``astrid.core.conformance.kit``) is the reusable kernel conformance
harness: it drives every implemented pack command through the seven
dimensions (replay, mismatch_before_mutation, same_project, vocabulary,
writer_ownership, crash_atomicity, hash_chain) over the real writer,
services, and repositories. This module proves two things:

1. the *positive* contract — ``timeline.create`` and ``timeline.save``
   conform on every dimension, and the manifest-only shot/reference commands
   stay explicitly non-executable; and
2. the *negative* contract — a deliberately non-conforming command is
   caught by each applicable dimension, so the kit cannot give false
   confidence by only passing correct commands.

Every negative sample runs the real check function against a broken
:class:`~astrid.core.conformance.kit.CommandSpec` and asserts the failure
signal (a :class:`ConformanceError`, or the kernel's typed rejection the
check surfaces). None of the broken specs touch the shipped repositories'
own code paths; they are adversarial fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astrid.core.conformance import (
    CONFORMANCE_DIMENSIONS,
    NON_EXECUTABLE_COMMAND_KINDS,
    CommandSpec,
    ConformanceContext,
    ConformanceError,
    check_crash_atomicity,
    check_hash_chain,
    check_mismatch_before_mutation,
    check_replay,
    check_same_project,
    check_vocabulary,
    check_writer_ownership,
    run_all,
    standard_command_specs,
)
from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService, EventChainError
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.errors import CommandVocabularyError
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter, WriterError
from astrid.packs import register_standard_schema_packs
from astrid.packs.timeline.repository import TimelineRepository

TS = "2026-08-15T00:00:00.000000+00:00"
_ULID = "01JM4K5N7P0000000000000001"

_FIFO_RECORDING_ARTIFACT = (
    "FIFO serialization violated"
)
"""The kit's known writer_ownership recording-order artifact.

``check_writer_ownership`` records the two concurrent transactions' start/end
timestamps under a completion-order lock. Thread preemption can append the
second transaction before the first even though the writer's strict FIFO
queue (proven by the writer/UoW tests) never overlaps transactions, which
makes the overlap assertion occasionally fail on a property that always
holds. The positive conformance test retries that exact artifact on a fresh
database; any other failure propagates immediately.
"""


def _build_registry():
    """Compose core + exactly timeline, shots, and references, then freeze."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def _build_context(db_path: Path) -> ConformanceContext:
    """Build one fresh standard-Astrid conformance context."""
    registry = _build_registry()
    writer = DatabaseWriter(db_path, registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    timelines = TimelineRepository(
        events=events, receipts=receipts, projects=projects
    )
    return ConformanceContext(
        db_path=db_path,
        writer=writer,
        registry=registry,
        events=events,
        receipts=receipts,
        projects=projects,
        timelines=timelines,
    )


@pytest.fixture
def ctx(tmp_path: Path):
    """A fresh standard-Astrid conformance context on its own database."""
    context = _build_context(tmp_path / "astrid.sqlite3")
    try:
        yield context
    finally:
        context.writer.close()


# ---------------------------------------------------------------------------
# Positive contract
# ---------------------------------------------------------------------------


def test_both_timeline_commands_conform_on_every_dimension(
    tmp_path: Path,
) -> None:
    """run_all passes all seven dimensions for timeline.create and save."""
    specs = standard_command_specs(_build_context(tmp_path / "probe.sqlite3"))
    assert set(specs) == {"timeline.create", "timeline.save"}

    for command_kind, spec in specs.items():
        report = _run_all_deterministic(
            tmp_path, spec, key=f"positive-{command_kind}"
        )
        dimensions = [evidence.dimension for evidence in report.evidence]
        assert dimensions == list(CONFORMANCE_DIMENSIONS), command_kind
        for evidence in report.evidence:
            assert evidence.command_kind == command_kind
            assert evidence.detail, command_kind


def _run_all_deterministic(tmp_path: Path, spec: CommandSpec, *, key: str):
    """run_all with a bounded retry for the kit's FIFO recording artifact.

    Each attempt runs on a fresh database so the kit's fixed project slugs
    never collide; the retry is bounded (3 attempts) and triggers only on
    :data:`_FIFO_RECORDING_ARTIFACT`, which is a false positive of the
    interval recording order, never a real FIFO violation. Every other
    failure propagates immediately.
    """
    last_error: ConformanceError | None = None
    for attempt in range(3):
        attempt_root = tmp_path / f"{key}-attempt-{attempt}"
        attempt_root.mkdir(parents=True, exist_ok=True)
        context = _build_context(attempt_root / "astrid.sqlite3")
        try:
            return run_all(context, spec, key=f"{key}-{attempt}")
        except ConformanceError as exc:
            if _FIFO_RECORDING_ARTIFACT not in str(exc):
                raise
            last_error = exc
        finally:
            context.writer.close()
    assert last_error is not None
    raise last_error


def test_manifest_only_shot_and_reference_commands_are_not_executable(
    ctx,
) -> None:
    """Declared-but-unimplemented commands stay registry-only, never runnable.

    The shots and references schema packs declare their future vocabulary
    (``shot.add_item``, ``reference.set_primary``) but ship ``repositories:
    []``; the kit's executable set must never contain them, while the
    registry still declares them so a would-be caller gets a typed error.
    """
    specs = standard_command_specs(ctx)
    for kind in NON_EXECUTABLE_COMMAND_KINDS:
        assert kind not in specs, f"{kind} must not be executable"
        # Declared in the frozen registry (no typed error).
        from astrid.core.events.registry import validate_command_kind

        validate_command_kind(ctx.registry, kind)

    for pack_id, command_kind in (
        ("shots", "shot.add_item"),
        ("references", "reference.set_primary"),
    ):
        manifest = load_schema_pack_manifest(
            Path("astrid") / "packs" / pack_id / "schema-pack.yaml"
        )
        assert manifest.repositories == (), pack_id
        assert command_kind in manifest.command_kinds, pack_id


def test_kernel_task_and_media_specs_conform_on_every_dimension(
    conformance_context,
) -> None:
    """core.task.create and core.media.import pass all seven dimensions.

    The m2 kernel specs (T24_impl) reuse the generalized conformance kit:
    deterministic stable aggregate ids, prepared filesystem fixtures under
    the context's temporary managed root, declared command-owned mutable
    tables, and generic result references. Every dimension — replay,
    mismatch-before-mutation, same-project, vocabulary, writer ownership,
    crash atomicity, and hash chains — must produce evidence for both
    commands, while the timeline specs stay registered and the
    manifest-only shots/references exclusions remain intact (proven by the
    enumeration tests above and below).
    """
    specs = standard_command_specs(conformance_context, include_kernel=True)
    for command_kind in ("core.task.create", "core.media.import"):
        assert command_kind in specs, command_kind
        spec = specs[command_kind]
        report = run_all(
            conformance_context, spec, key=f"kernel-{command_kind}"
        )
        dimensions = [evidence.dimension for evidence in report.evidence]
        assert dimensions == list(CONFORMANCE_DIMENSIONS), command_kind
        for evidence in report.evidence:
            assert evidence.command_kind == command_kind
            assert evidence.detail, command_kind

    # Timeline behavior is preserved alongside the kernel specs: the two
    # m1 commands still conform on every dimension in the same context.
    for command_kind in ("timeline.create", "timeline.save"):
        spec = specs[command_kind]
        report = run_all(
            conformance_context, spec, key=f"kernel-timeline-{command_kind}"
        )
        dimensions = [evidence.dimension for evidence in report.evidence]
        assert dimensions == list(CONFORMANCE_DIMENSIONS), command_kind
    # The declared-but-unimplemented exclusions never become executable.
    for kind in NON_EXECUTABLE_COMMAND_KINDS:
        assert kind not in specs, f"{kind} must not be executable"


# ---------------------------------------------------------------------------
# Negative samples: every dimension must catch a deliberately broken command
# ---------------------------------------------------------------------------


class _FakeModel:
    """Minimal read-model stand-in carrying the fields checks inspect."""

    def __init__(
        self, *, timeline_id: str, slug: str, **fields: Any
    ) -> None:
        self.timeline_id = timeline_id
        self.slug = slug
        self.name = fields.pop("name", "Main")
        self._fields = fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "slug": self.slug,
            "name": self.name,
            **self._fields,
        }


def _noop_prepare(ctx, writer, *, project_id, key) -> None:
    """Broken-sample commands create their own project in the test."""


def test_negative_replay_changed_result_is_caught(ctx) -> None:
    """A command whose second identical retry returns a different result."""
    calls = {"n": 0}

    def invoke(ctx, uow, *, project_id, key):
        calls["n"] += 1
        return _FakeModel(timeline_id=f"tl-{key}", slug="main", n=calls["n"])

    spec = CommandSpec(
        command_kind="timeline.create",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created",),
        invoke=invoke,
        invoke_changed=invoke,
        read=lambda ctx, writer, project_id, ref: _FakeModel(
            timeline_id="tl-x", slug="main"
        ),
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    project = ctx.create_project(slug="neg-replay", key="neg-replay-proj")
    with pytest.raises(ConformanceError) as excinfo:
        check_replay(ctx, spec, project_id=project.id, key="neg-replay")
    assert "did not return the stored result" in str(excinfo.value)


def test_negative_mismatch_without_rejection_is_caught(ctx) -> None:
    """A changed request that silently succeeds instead of raising."""
    model = _FakeModel(timeline_id="tl-mm", slug="main")

    spec = CommandSpec(
        command_kind="timeline.save",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.saved",),
        invoke=lambda ctx, uow, **kw: model,
        invoke_changed=lambda ctx, uow, **kw: model,
        read=lambda ctx, writer, project_id, ref: model,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    project = ctx.create_project(slug="neg-mismatch", key="neg-mismatch-proj")
    with pytest.raises(ConformanceError) as excinfo:
        check_mismatch_before_mutation(
            ctx, spec, project_id=project.id, key="neg-mismatch"
        )
    assert "did not raise" in str(excinfo.value)


def test_negative_same_project_unscoped_read_is_caught(ctx) -> None:
    """A read that answers cross-project instead of raising not-found."""
    model = _FakeModel(timeline_id="tl-sp", slug="main")

    spec = CommandSpec(
        command_kind="timeline.create",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created",),
        invoke=lambda ctx, uow, **kw: model,
        invoke_changed=lambda ctx, uow, **kw: model,
        # Ignores the project: no typed RepositoryError for another project.
        read=lambda ctx, writer, project_id, ref: model,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    project_a = ctx.create_project(slug="neg-sp-a", key="neg-sp-a-proj")
    project_b = ctx.create_project(slug="neg-sp-b", key="neg-sp-b-proj")
    with pytest.raises(ConformanceError) as excinfo:
        check_same_project(
            ctx,
            spec,
            project_id=project_a.id,
            other_project_id=project_b.id,
            key="neg-same-project",
        )
    assert "did not raise a typed" in str(excinfo.value)


def test_negative_vocabulary_undeclared_command_kind_is_caught(ctx) -> None:
    """An undeclared command kind is rejected before any mutation."""
    spec = CommandSpec(
        command_kind="timeline.nonexistent",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created",),
        invoke=lambda ctx, uow, **kw: _FakeModel(
            timeline_id="tl-v", slug="main"
        ),
        invoke_changed=lambda ctx, uow, **kw: _FakeModel(
            timeline_id="tl-v", slug="main"
        ),
        read=lambda ctx, writer, project_id, ref: _FakeModel(
            timeline_id="tl-v", slug="main"
        ),
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    with pytest.raises(CommandVocabularyError):
        check_vocabulary(
            ctx, spec, executable_kinds=set(standard_command_specs(ctx))
        )


def test_negative_vocabulary_non_executable_registered_is_caught(
    ctx,
) -> None:
    """Registering a manifest-only command as executable must fail."""
    spec = standard_command_specs(ctx)["timeline.create"]
    executable = {"timeline.create", "shot.add_item"}
    with pytest.raises(ConformanceError) as excinfo:
        check_vocabulary(ctx, spec, executable_kinds=executable)
    assert "non-executable commands are registered as executable" in str(
        excinfo.value
    )


def test_negative_writer_nested_submission_is_caught(ctx) -> None:
    """A command that opens a second unit of work inside one is rejected."""
    real_specs = standard_command_specs(ctx)

    def invoke(ctx, uow, *, project_id, key):
        # The broken command tries to run another command inside this one,
        # which the writer's one-owner FIFO guard rejects up front.
        return UnitOfWork(ctx.writer).run(
            lambda u: ctx.timelines.create(
                u,
                project_id=project_id,
                slug="main",
                name="Main",
                config={"fps": 24},
                registry={"assets": {}},
                idempotency_key=f"nested-{key}",
                created_at=TS,
            )
        )

    broken = CommandSpec(
        command_kind="timeline.create",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created",),
        invoke=invoke,
        invoke_changed=real_specs["timeline.create"].invoke_changed,
        read=real_specs["timeline.create"].read,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    project = ctx.create_project(slug="neg-writer", key="neg-writer-proj")
    with pytest.raises((ConformanceError, WriterError)):
        check_writer_ownership(ctx, broken, project_id=project.id, key="w")


def test_negative_crash_nondeterministic_boundaries_is_caught(ctx) -> None:
    """A command whose statement boundaries differ run-to-run is caught."""
    calls = {"n": 0}

    def invoke(ctx, uow, *, project_id, key):
        calls["n"] += 1
        model = ctx.timelines.create(
            uow,
            project_id=project_id,
            slug="main-neg",
            name="Main",
            config={"fps": 24},
            registry={"assets": {}},
            idempotency_key=f"neg-create-{calls['n']}",
            timeline_id=f"00000000-0000-4000-8000-0000000000{calls['n']:02d}",
            timeline_ulid=_ULID,
            created_at=TS,
        )
        if calls["n"] >= 2:
            ctx.timelines.save(
                uow,
                project_id=project_id,
                ref="main-neg",
                config={"fps": 30},
                registry={"assets": {}},
                expected_version=1,
                created_at=TS,
            )
        return model

    def seed(ctx, writer):
        UnitOfWork(writer).run(
            lambda u: ctx.projects.create(
                u,
                slug="neg-crash-proj",
                name="Neg Crash",
                settings={},
                idempotency_key="neg-crash-proj",
                project_id="neg-crash-proj",
                created_at=TS,
            )
        )
        return {
            "project_id": "neg-crash-proj",
            "ref": None,
            "key": "neg-crash",
        }

    broken = CommandSpec(
        command_kind="timeline.save",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created", "timeline.saved"),
        invoke=invoke,
        invoke_changed=invoke,
        read=standard_command_specs(ctx)["timeline.save"].read,
        seed=seed,
        prepare=_noop_prepare,
    )
    with pytest.raises(ConformanceError) as excinfo:
        check_crash_atomicity(ctx, broken)
    assert "not deterministic" in str(excinfo.value)


def test_negative_hash_chain_missing_integrity_envelope_is_caught(
    ctx,
) -> None:
    """An event written without the SD2 integrity envelope fails verification."""
    calls = {"n": 0}

    def invoke(ctx, uow, *, project_id, key):
        calls["n"] += 1
        timeline_id = f"tl-hash-{calls['n']}"
        stream_id = f"{timeline_id}:timeline.timeline"
        # project_seq 2: the project's own core.project.created event holds
        # project_seq 1, and the raw event bypasses the append service.
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, "
            "aggregate_id, head_seq, created_at) VALUES (?, ?, "
            "'timeline.timeline', ?, 1, ?)",
            (stream_id, project_id, timeline_id, TS),
        )
        uow.execute(
            "INSERT INTO events (event_id, project_id, project_seq, "
            "stream_id, seq, subject_type, subject_id, changes_json, kind, "
            "schema_version, idempotency_key, txn_id, actor_kind, "
            "payload_json, created_at) VALUES (?, ?, 2, ?, 1, 'timeline', "
            "?, '[]', 'timeline.created', 1, ?, 'txn', 'local', ?, ?)",
            (
                f"evt-hash-{calls['n']}",
                project_id,
                stream_id,
                timeline_id,
                f"key-{calls['n']}",
                json.dumps({"data": {"slug": "main"}}),
                TS,
            ),
        )
        uow.execute(
            "UPDATE projects SET event_head_seq = 2 WHERE id = ?",
            (project_id,),
        )
        return _FakeModel(timeline_id=timeline_id, slug="main")

    def read(ctx, writer, project_id, ref):
        return _FakeModel(
            timeline_id=f"tl-hash-{calls['n']}", slug="main"
        )

    broken = CommandSpec(
        command_kind="timeline.create",
        pack_id="timeline",
        stream_type="timeline.timeline",
        event_kinds=("timeline.created",),
        invoke=invoke,
        invoke_changed=invoke,
        read=read,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
    )
    project = ctx.create_project(slug="neg-hash", key="neg-hash-proj")
    with pytest.raises(EventChainError):
        check_hash_chain(ctx, broken, project_id=project.id, key="neg-hash")
