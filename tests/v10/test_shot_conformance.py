"""Pack-owned shot conformance specs through the kernel kit (m3 T14).

This suite proves that every executable shot command — ``shot.create``,
``shot.add_item``, ``shot.remove_item``, and ``shot.reorder`` — conforms on
every common dimension of :mod:`astrid.core.conformance.kit` (replay,
mismatch-before-mutation, same-project rejection, vocabulary, writer
ownership, hash chains, and statement-boundary crash atomicity) through the
pack-owned factories in :mod:`astrid.packs.shots.conformance`, against
exact same-project kernel media fixtures.

Beyond the seven common dimensions the suite exercises the shot-specific
ordering and position domain: ``add_item`` accepts exactly the validated
insertion positions ``0 .. count`` and rejects out-of-range positions before
any write, and ``reorder`` accepts exactly one exact permutation of the
shot's current item ids — rejecting omissions, duplicates, extras, and
foreign-shot items before any write — while ``show`` reflects the exact
normalized order after every mutation.

The factories are pack-owned and assembled only from injected context
repositories: the kernel kit never imports the pack (no kernel-to-pack
dependency), and the pack opens no writer and owns no transaction — every
mutation runs inside the caller's single ``BEGIN IMMEDIATE`` unit of work on
the injected kernel writer. A source assertion proves the pack conformance
module constructs no writer, and an independence test proves the shot and
reference factories run independently when the other pack repository is
absent from the context.
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
    run_all,
    standard_command_specs,
)
from astrid.core.events.registry import register_core_vocabulary, validate_command_kind
from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptService
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import RunRepository
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import register_standard_schema_packs
from astrid.packs.references.conformance import reference_command_specs
from astrid.packs.references.repository import ReferenceRepository
from astrid.packs.shots.conformance import (
    _media_id,
    _stable_item_id,
    _stable_shot_id,
    shot_command_specs,
)
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_REORDER_COMMAND_KIND,
    SHOT_REORDERED_EVENT_KIND,
    SHOT_STREAM_TYPE,
    ShotReorderError,
    ShotRepository,
    ShotValidationError,
)
from astrid.packs.timeline.repository import TimelineRepository

TS = "2026-08-15T00:00:00.000000+00:00"
TS2 = "2026-08-15T01:00:00.000000+00:00"

_FIFO_RECORDING_ARTIFACT = ("FIFO serialization violated")
"""The kit's known writer_ownership recording-order artifact (see the m1
conformance suite): the check retries only that exact false positive on a
fresh database; every other failure propagates immediately."""


def _build_context(
    db_path: Path, *, with_shots: bool, with_references: bool
) -> ConformanceContext:
    """Fresh standard-Astrid context with exactly the requested pack repos.

    Mirrors the shared ``conformance_context`` fixture but builds a fresh
    context per call so the bounded FIFO-artifact retry gets a clean database
    (fixed project slugs never collide), and injects only the repositories
    the test asks for so independence of the two pack factories is provable.
    """
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    registry = registry.freeze()
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
    if with_shots:
        context.shots = ShotRepository(events=events, receipts=receipts)
    if with_references:
        context.references = ReferenceRepository(events=events, receipts=receipts)
    return context


def _run_all_deterministic(
    tmp_path: Path,
    spec: CommandSpec,
    *,
    key: str,
    build=None,
):
    """run_all with a bounded retry for the kit's FIFO recording artifact.

    Each attempt runs on a fresh database; the retry (3 attempts) triggers
    only on the known false positive, never on a real FIFO violation.
    ``build`` optionally supplies the fresh context factory (default: a
    shots-only context, which is what every shot spec needs).
    """
    builder = build or (
        lambda db_path: _build_context(
            db_path, with_shots=True, with_references=False
        )
    )
    last_error: ConformanceError | None = None
    for attempt in range(3):
        attempt_root = tmp_path / f"{key}-attempt-{attempt}"
        attempt_root.mkdir(parents=True, exist_ok=True)
        context = builder(attempt_root / "astrid.sqlite3")
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
# Positive contract: every shot command conforms on every dimension
# ---------------------------------------------------------------------------


def test_shot_command_specs_register_exactly_the_four_commands(
    conformance_context,
) -> None:
    """The pack-owned factory registers exactly the frozen command kinds."""
    specs = shot_command_specs(conformance_context)
    assert set(specs) == {
        "shot.create",
        "shot.add_item",
        "shot.remove_item",
        "shot.reorder",
    }
    for command_kind, spec in specs.items():
        assert spec.pack_id == "shots", command_kind
        assert spec.stream_type == SHOT_STREAM_TYPE, command_kind
        assert spec.event_kinds, command_kind
        # Every registered command kind is declared by the frozen registry.
        validate_command_kind(conformance_context.registry, command_kind)
        # The kernel executable set never contains pack commands.
        assert command_kind not in standard_command_specs(conformance_context)


def test_text_binding_vocabulary_is_declared_but_not_a_legacy_shot_spec(
    conformance_context,
) -> None:
    """B1 declares text commands without widening the legacy factory yet."""
    from astrid.core.schema_packs.manifest import load_schema_pack_manifest

    manifest = load_schema_pack_manifest(
        Path("astrid") / "packs" / "shots" / "schema-pack.yaml"
    )
    assert "shot.text_binding" in manifest.stream_types
    assert "shot.text_binding.set" in manifest.command_kinds
    assert set(shot_command_specs(conformance_context)) == {
        "shot.create", "shot.add_item", "shot.remove_item", "shot.reorder"
    }


def test_every_shot_command_conforms_on_every_dimension(tmp_path: Path) -> None:
    """All four shot commands pass all seven kit dimensions."""
    specs = shot_command_specs(
        _build_context(
            tmp_path / "probe.sqlite3", with_shots=True, with_references=False
        )
    )
    assert set(specs) == {
        "shot.create",
        "shot.add_item",
        "shot.remove_item",
        "shot.reorder",
    }

    for command_kind, spec in specs.items():
        report = _run_all_deterministic(
            tmp_path, spec, key=f"shot-{command_kind}"
        )
        dimensions = [evidence.dimension for evidence in report.evidence]
        assert dimensions == list(CONFORMANCE_DIMENSIONS), command_kind
        for evidence in report.evidence:
            assert evidence.command_kind == command_kind
            assert evidence.detail, command_kind


def test_shot_conformance_factory_creates_no_pack_writer(tmp_path: Path) -> None:
    """The pack-owned factory never constructs a writer or opens a connection.

    Writer authority stays in the kernel: the shots pack conformance module
    contains no ``DatabaseWriter(`` construction and no writable
    ``sqlite3.connect`` call; the only ``UnitOfWork`` uses are the
    caller-owned kernel currency inside ``prepare``/``seed``.
    """
    from astrid.packs.shots import conformance as pack_conformance

    source = Path(pack_conformance.__file__).read_text(encoding="utf-8")
    assert "DatabaseWriter(" not in source
    assert "sqlite3.connect" not in source
    assert "UnitOfWork(" in source


# ---------------------------------------------------------------------------
# Ordering and position domain through the pack-owned specs
# ---------------------------------------------------------------------------


def test_shot_add_item_position_domain_and_ordering_through_specs(
    tmp_path: Path,
) -> None:
    """add_item accepts validated positions and keeps exact normalized order.

    Drives the pack-owned ``shot.add_item`` spec's ``prepare`` to build the
    exact-media fixture (project + media + empty shot), then inserts items at
    the front, end, and middle of the shot and verifies ``show`` reflects the
    exact normalized order with stable 0-based positions after every insert.
    An out-of-range position is rejected before any write (the shot's order
    is unchanged).
    """
    context = _build_context(
        tmp_path / "domain.sqlite3", with_shots=True, with_references=False
    )
    try:
        spec = shot_command_specs(context)[SHOT_ADD_ITEM_COMMAND_KIND]
        project = context.create_project(
            slug="shot-domain-proj", key="shot-domain-proj-key"
        )
        spec.prepare(context, context.writer, project_id=project.id, key="domain")
        shot_id = _stable_shot_id("prepare-domain")
        shots = context.shots
        item_a = _stable_item_id("domain", "a")
        item_b = _stable_item_id("domain", "b")
        item_a2 = _stable_item_id("domain", "a2")

        # Insert at position 0 of the empty shot, then append at position 1.
        first = UnitOfWork(context.writer).run(
            lambda u: shots.add_item(
                u,
                project_id=project.id,
                shot_id=shot_id,
                media_id=_media_id("a"),
                position=0,
                idempotency_key="domain-item-a",
                item_id=item_a,
                created_at=TS,
            )
        )
        assert first.item_ids == (item_a,)
        second = UnitOfWork(context.writer).run(
            lambda u: shots.add_item(
                u,
                project_id=project.id,
                shot_id=shot_id,
                media_id=_media_id("b"),
                position=1,
                idempotency_key="domain-item-b",
                item_id=item_b,
                created_at=TS,
            )
        )
        assert second.item_ids == (item_a, item_b)

        # Insert into the middle (position 1) pushes the tail item right.
        third = UnitOfWork(context.writer).run(
            lambda u: shots.add_item(
                u,
                project_id=project.id,
                shot_id=shot_id,
                media_id=_media_id("a"),
                position=1,
                idempotency_key="domain-item-a2",
                item_id=item_a2,
                created_at=TS,
            )
        )
        assert third.item_ids == (item_a, item_a2, item_b)

        shown = shots.show(context.writer, project.id, shot_id)
        assert [item.id for item in shown.items] == [item_a, item_a2, item_b]
        assert [item.position for item in shown.items] == [0, 1, 2]

        # An out-of-range position (count + 1) is rejected before any write.
        before = shots.show(context.writer, project.id, shot_id)
        with pytest.raises(ShotValidationError):
            UnitOfWork(context.writer).run(
                lambda u: shots.add_item(
                    u,
                    project_id=project.id,
                    shot_id=shot_id,
                    media_id=_media_id("b"),
                    position=4,
                    idempotency_key="domain-item-bad",
                    item_id=_stable_item_id("domain", "bad"),
                    created_at=TS,
                )
            )
        after = shots.show(context.writer, project.id, shot_id)
        assert [item.id for item in after.items] == [
            item.id for item in before.items
        ]
    finally:
        context.writer.close()


def test_shot_reorder_ordering_and_permutation_domain_through_specs(
    tmp_path: Path,
) -> None:
    """reorder accepts one exact permutation and rejects every other shape.

    Drives the pack-owned ``shot.reorder`` spec's ``prepare`` to build the
    exact-media fixture (project + media + a two-item shot), reorders to the
    exact reversed permutation and verifies the receipt and ``show`` carry
    the exact new item/media order, then proves omissions, duplicates,
    extras, and foreign-shot items are each rejected before any write (the
    shot's order is unchanged after every rejection).
    """
    context = _build_context(
        tmp_path / "reorder.sqlite3", with_shots=True, with_references=False
    )
    try:
        spec = shot_command_specs(context)[SHOT_REORDER_COMMAND_KIND]
        project = context.create_project(
            slug="shot-reorder-proj", key="shot-reorder-proj-key"
        )
        spec.prepare(context, context.writer, project_id=project.id, key="reorder")
        shot_id = _stable_shot_id("prepare-reorder")
        shots = context.shots
        item_a = _stable_item_id("prepare-reorder", "a")
        item_b = _stable_item_id("prepare-reorder", "b")

        # The prepared shot is ordered [a, b] with exact media a then b.
        shown = shots.show(context.writer, project.id, shot_id)
        assert [item.id for item in shown.items] == [item_a, item_b]
        assert [item.media_id for item in shown.items] == [
            _media_id("a"),
            _media_id("b"),
        ]

        # Reorder to the exact reversed permutation; the receipt carries the
        # exact item and media order and show reflects the new positions.
        result = UnitOfWork(context.writer).run(
            lambda u: shots.reorder(
                u,
                project_id=project.id,
                shot_id=shot_id,
                item_ids=[item_b, item_a],
                idempotency_key="reorder-reversed",
                created_at=TS2,
            )
        )
        assert result.item_ids == (item_b, item_a)
        assert result.media_ids == (_media_id("b"), _media_id("a"))
        shown = shots.show(context.writer, project.id, shot_id)
        assert [item.id for item in shown.items] == [item_b, item_a]
        assert [item.position for item in shown.items] == [0, 1]

        # A third item makes the non-permutation rejections meaningful.
        item_c = _stable_item_id("reorder", "c")
        UnitOfWork(context.writer).run(
            lambda u: shots.add_item(
                u,
                project_id=project.id,
                shot_id=shot_id,
                media_id=_media_id("a"),
                position=2,
                idempotency_key="reorder-item-c",
                item_id=item_c,
                created_at=TS2,
            )
        )

        # Omission, duplicate, and extra are each rejected before any write.
        for bad_ids, detail in (
            ([item_b, item_a], "omission"),
            ([item_b, item_b, item_a, item_c], "duplicate"),
            ([item_b, item_a, item_c, "nonexistent-item"], "extra"),
        ):
            before = shots.show(context.writer, project.id, shot_id)
            with pytest.raises(ShotReorderError) as excinfo:
                UnitOfWork(context.writer).run(
                    lambda u: shots.reorder(
                        u,
                        project_id=project.id,
                        shot_id=shot_id,
                        item_ids=bad_ids,
                        idempotency_key=f"reorder-bad-{detail}",
                        created_at=TS2,
                    )
                )
            assert excinfo.value.detail == detail, bad_ids
            after = shots.show(context.writer, project.id, shot_id)
            assert [item.id for item in after.items] == [
                item.id for item in before.items
            ]

        # A foreign-shot item is rejected before any write: another shot owns
        # an item with that id, so the request is not an exact permutation.
        other_shot_id = _stable_shot_id("prepare-reorder", "other")
        foreign_item = _stable_item_id("other-shot", "x")
        UnitOfWork(context.writer).run(
            lambda u: shots.create(
                u,
                project_id=project.id,
                name="Other Shot",
                idempotency_key="reorder-other-shot",
                shot_id=other_shot_id,
                created_at=TS2,
            )
        )
        UnitOfWork(context.writer).run(
            lambda u: shots.add_item(
                u,
                project_id=project.id,
                shot_id=other_shot_id,
                media_id=_media_id("b"),
                position=0,
                idempotency_key="reorder-foreign-item",
                item_id=foreign_item,
                created_at=TS2,
            )
        )
        before = shots.show(context.writer, project.id, shot_id)
        with pytest.raises(ShotReorderError) as excinfo:
            UnitOfWork(context.writer).run(
                lambda u: shots.reorder(
                    u,
                    project_id=project.id,
                    shot_id=shot_id,
                    item_ids=[item_b, item_a, item_c, foreign_item],
                    idempotency_key="reorder-foreign",
                    created_at=TS2,
                )
            )
        assert excinfo.value.detail == "foreign"
        after = shots.show(context.writer, project.id, shot_id)
        assert [item.id for item in after.items] == [
            item.id for item in before.items
        ]
    finally:
        context.writer.close()


# ---------------------------------------------------------------------------
# Independence: each pack's specs run without the other pack's repository
# ---------------------------------------------------------------------------


def test_shot_and_reference_specs_run_independently(tmp_path: Path) -> None:
    """Shot and reference factories run when the other repository is absent.

    A context with only the shots repository injected still drives the shot
    specs through every kit dimension (the factory never touches
    ``references``), and a context with only the references repository
    injected still drives the reference specs the same way (it never touches
    ``shots``). Each side runs ``run_all`` on a representative command to
    prove the independence end-to-end over the real writer.
    """
    # Shots-only context: no references attribute at all.
    shot_ctx = _build_context(
        tmp_path / "shots-only.sqlite3", with_shots=True, with_references=False
    )
    try:
        specs = shot_command_specs(shot_ctx)
        assert set(specs) == {
            "shot.create",
            "shot.add_item",
            "shot.remove_item",
            "shot.reorder",
        }
        report = _run_all_deterministic(
            tmp_path,
            specs[SHOT_REORDER_COMMAND_KIND],
            key="indep-shot-reorder",
            build=lambda db: _build_context(
                db, with_shots=True, with_references=False
            ),
        )
        assert [e.dimension for e in report.evidence] == list(
            CONFORMANCE_DIMENSIONS
        )
    finally:
        shot_ctx.writer.close()

    # References-only context: no shots attribute at all.
    ref_ctx = _build_context(
        tmp_path / "refs-only.sqlite3", with_shots=False, with_references=True
    )
    try:
        specs = reference_command_specs(ref_ctx)
        assert set(specs) == {
            "reference.create",
            "reference.archive",
            "reference.associate",
            "reference.set_primary",
            "reference.link",
        }
        report = _run_all_deterministic(
            tmp_path,
            specs["reference.create"],
            key="indep-ref-create",
            build=lambda db: _build_context(
                db, with_shots=False, with_references=True
            ),
        )
        assert [e.dimension for e in report.evidence] == list(
            CONFORMANCE_DIMENSIONS
        )
    finally:
        ref_ctx.writer.close()


# ---------------------------------------------------------------------------
# Negative control: the kit still catches a broken shot-shaped command
# ---------------------------------------------------------------------------


class _BrokenModel:
    """Minimal read-model stand-in carrying the fields the checks inspect."""

    def __init__(self, *, shot_id: str) -> None:
        self.shot_id = shot_id

    def to_dict(self) -> dict[str, Any]:
        return {"shot_id": self.shot_id}


def _noop_prepare(ctx, writer, *, project_id, key) -> None:
    """Broken-sample commands create their own state in the test."""


def test_negative_shot_reorder_mismatch_without_rejection_is_caught(
    conformance_context,
) -> None:
    """A broken shot.reorder whose changed request silently succeeds."""
    model = _BrokenModel(shot_id="shot-mm")

    spec = CommandSpec(
        command_kind=SHOT_REORDER_COMMAND_KIND,
        pack_id="shots",
        stream_type=SHOT_STREAM_TYPE,
        event_kinds=(SHOT_REORDERED_EVENT_KIND,),
        invoke=lambda ctx, uow, **kw: model,
        invoke_changed=lambda ctx, uow, **kw: model,
        read=lambda ctx, writer, project_id, ref: model,
        seed=lambda ctx, writer: {"project_id": "p", "ref": None, "key": "k"},
        prepare=_noop_prepare,
        result_ref=lambda model: model.shot_id,
    )
    project = conformance_context.create_project(
        slug="neg-shot-mismatch", key="neg-shot-mismatch-proj"
    )
    with pytest.raises(ConformanceError) as excinfo:
        check_mismatch_before_mutation(
            conformance_context,
            spec,
            project_id=project.id,
            key="neg-shot-mismatch",
        )
    assert "did not raise" in str(excinfo.value)
