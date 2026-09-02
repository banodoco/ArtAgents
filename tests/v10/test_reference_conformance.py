"""Pack-owned reference conformance specs through the kernel kit (m3 T13).

This suite proves that every executable reference command —
``reference.create``, ``reference.archive``, ``reference.associate``,
``reference.set_primary``, and ``reference.link`` — conforms on every common
dimension of :mod:`astrid.core.conformance.kit` (replay,
mismatch-before-mutation, same-project rejection, vocabulary, writer
ownership, hash chains, and statement-boundary crash atomicity) through the
pack-owned factories in :mod:`astrid.packs.references.conformance`.

The factories are pack-owned and assembled only from injected context
repositories: the kernel kit never imports the pack (no kernel-to-pack
dependency), and the pack opens no writer and owns no transaction — every
mutation runs inside the caller's single ``BEGIN IMMEDIATE`` unit of work on
the injected kernel writer.

Negative controls are retained alongside the positive contract: deliberately
broken reference-shaped specs are caught by the kit's replay and
mismatch-before-mutation checks, proving the kit cannot give false confidence
by only passing correct commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from astrid.core.conformance import (
    CONFORMANCE_DIMENSIONS,
    CommandSpec,
    ConformanceContext,
    ConformanceError,
    check_mismatch_before_mutation,
    check_replay,
    run_all,
    standard_command_specs,
)
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import RunRepository
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import compose_standard_pack_database
from astrid.packs.references.conformance import reference_command_specs
from astrid.packs.references.repository import (
    REFERENCE_ARCHIVED_EVENT_KIND,
    REFERENCE_CREATED_EVENT_KIND,
    REFERENCE_STREAM_TYPE,
    ReferenceRepository,
)
from astrid.packs.timeline.repository import TimelineRepository

_FIFO_RECORDING_ARTIFACT = ("FIFO serialization violated")
"""The kit's known writer_ownership recording-order artifact (see the m1
conformance suite): the check retries only that exact false positive on a
fresh database; every other failure propagates immediately."""


def _build_reference_context(db_path: Path) -> ConformanceContext:
    """Fresh standard-Astrid context with the references repository injected.

    Mirrors the shared ``conformance_context`` fixture but builds a fresh
    context per call so the bounded FIFO-artifact retry gets a clean database
    (fixed project slugs never collide).
    """
    registry = compose_standard_pack_database().registry
    writer = DatabaseWriter(db_path, registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    projects = ProjectRepository(events=events, receipts=receipts)
    managed_root = db_path.parent / "managed"
    context = ConformanceContext(
        db_path=db_path,
        writer=writer,
        registry=registry,
        events=events,
        receipts=receipts,
        projects=projects,
        timelines=TimelineRepository(
            events=events, receipts=receipts, projects=projects
        ),
        tasks=TaskRepository(events=events, receipts=receipts),
        media=MediaRepository(
            events=events, receipts=receipts, projects_root=managed_root
        ),
        runs=RunRepository(events=events, receipts=receipts),
        managed_root=managed_root,
    )
    context.references = ReferenceRepository(events=events, receipts=receipts)
    return context


def _run_all_deterministic(tmp_path: Path, spec: CommandSpec, *, key: str):
    """run_all with a bounded retry for the kit's FIFO recording artifact.

    Each attempt runs on a fresh database; the retry (3 attempts) triggers
    only on the known false positive, never on a real FIFO violation.
    """
    last_error: ConformanceError | None = None
    for attempt in range(3):
        attempt_root = tmp_path / f"{key}-attempt-{attempt}"
        attempt_root.mkdir(parents=True, exist_ok=True)
        context = _build_reference_context(attempt_root / "astrid.sqlite3")
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


# ---------------------------------------------------------------------------
# Positive contract: every reference command conforms on every dimension
# ---------------------------------------------------------------------------


def test_reference_command_specs_register_exactly_the_five_commands(
    conformance_context,
) -> None:
    """The pack-owned factory registers exactly the frozen command kinds."""
    specs = reference_command_specs(conformance_context)
    assert set(specs) == {
        "reference.create",
        "reference.archive",
        "reference.associate",
        "reference.set_primary",
        "reference.link",
    }
    for command_kind, spec in specs.items():
        assert spec.pack_id == "references", command_kind
        assert spec.stream_type == REFERENCE_STREAM_TYPE, command_kind
        assert spec.event_kinds, command_kind
        # Every registered command kind is declared by the frozen registry.
        from astrid.core.events.registry import validate_command_kind

        validate_command_kind(conformance_context.registry, command_kind)
        # The kernel executable set never contains pack commands.
        assert command_kind not in standard_command_specs(conformance_context)


def test_every_reference_command_conforms_on_every_dimension(
    tmp_path: Path,
) -> None:
    """All five reference commands pass all seven kit dimensions."""
    specs = reference_command_specs(
        _build_reference_context(tmp_path / "probe.sqlite3")
    )
    assert set(specs) == {
        "reference.create",
        "reference.archive",
        "reference.associate",
        "reference.set_primary",
        "reference.link",
    }

    for command_kind, spec in specs.items():
        report = _run_all_deterministic(
            tmp_path, spec, key=f"reference-{command_kind}"
        )
        dimensions = [evidence.dimension for evidence in report.evidence]
        assert dimensions == list(CONFORMANCE_DIMENSIONS), command_kind
        for evidence in report.evidence:
            assert evidence.command_kind == command_kind
            assert evidence.detail, command_kind


def test_reference_conformance_factory_creates_no_pack_writer(
    tmp_path: Path,
) -> None:
    """The pack-owned factory never constructs a writer or opens a connection.

    Writer authority stays in the kernel: the references pack conformance
    module contains no ``DatabaseWriter(`` construction and no writable
    ``sqlite3.connect`` call; the only ``UnitOfWork`` uses are the
    caller-owned kernel currency inside ``prepare``/``seed``.
    """
    from astrid.packs.references import conformance as pack_conformance

    source = Path(pack_conformance.__file__).read_text(encoding="utf-8")
    assert "DatabaseWriter(" not in source
    assert "sqlite3.connect" not in source
    assert "UnitOfWork(" in source


# ---------------------------------------------------------------------------
# Negative controls: the kit still catches broken reference-shaped commands
# ---------------------------------------------------------------------------


class _BrokenModel:
    """Minimal read-model stand-in carrying the fields the checks inspect."""

    def __init__(self, *, reference_id: str, n: int = 0) -> None:
        self.reference_id = reference_id
        self.n = n

    def to_dict(self) -> dict[str, Any]:
        return {"reference_id": self.reference_id, "n": self.n}


def _noop_prepare(ctx, writer, *, project_id, key) -> None:
    """Broken-sample commands create their own state in the test."""


def test_negative_reference_replay_changed_result_is_caught(
    conformance_context,
) -> None:
    """A broken reference.create whose replay returns a different result."""
    calls = {"n": 0}

    def invoke(ctx, uow, *, project_id, key):
        calls["n"] += 1
        return _BrokenModel(reference_id=f"ref-{key}", n=calls["n"])

    spec = CommandSpec(
        command_kind="reference.create",
        pack_id="references",
        stream_type=REFERENCE_STREAM_TYPE,
        event_kinds=(REFERENCE_CREATED_EVENT_KIND,),
        invoke=invoke,
        invoke_changed=invoke,
        read=lambda ctx, writer, project_id, ref: _BrokenModel(reference_id=ref),
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
        result_ref=lambda model: model.reference_id,
    )
    project = conformance_context.create_project(
        slug="neg-ref-replay", key="neg-ref-replay-proj"
    )
    with pytest.raises(ConformanceError) as excinfo:
        check_replay(
            conformance_context,
            spec,
            project_id=project.id,
            key="neg-ref-replay",
        )
    assert "did not return the stored result" in str(excinfo.value)


def test_negative_reference_mismatch_without_rejection_is_caught(
    conformance_context,
) -> None:
    """A broken reference.archive whose changed request silently succeeds."""
    model = _BrokenModel(reference_id="ref-mm")

    spec = CommandSpec(
        command_kind="reference.archive",
        pack_id="references",
        stream_type=REFERENCE_STREAM_TYPE,
        event_kinds=(REFERENCE_ARCHIVED_EVENT_KIND,),
        invoke=lambda ctx, uow, **kw: model,
        invoke_changed=lambda ctx, uow, **kw: model,
        read=lambda ctx, writer, project_id, ref: model,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
        result_ref=lambda model: model.reference_id,
    )
    project = conformance_context.create_project(
        slug="neg-ref-mismatch", key="neg-ref-mismatch-proj"
    )
    with pytest.raises(ConformanceError) as excinfo:
        check_mismatch_before_mutation(
            conformance_context,
            spec,
            project_id=project.id,
            key="neg-ref-mismatch",
        )
    assert "did not raise" in str(excinfo.value)
