"""Pack-owned conformance CommandSpec factories for the shots pack (m3 T14).

The shots pack owns the executable command surface
(:class:`~astrid.packs.shots.repository.ShotRepository`); this module
defines the four pack-owned
:class:`~astrid.core.conformance.kit.CommandSpec` factories —
``shot.create``, ``shot.add_item``, ``shot.remove_item``, and
``shot.reorder`` — that drive the kernel conformance kit over the real
repositories on the real kernel writer.

The architecture boundary stays clean: this module imports only kernel code
(the conformance kit, media import, receipts, UoW) and its own pack — the
kernel kit never imports a pack, so ``astrid/core`` stays free of pack
imports (m3 watch item; T16 lint).

Every spec exercises the seven kit dimensions — replay, mismatch-before-
mutation, same-project rejection, vocabulary, writer ownership, hash chains,
and statement-boundary crash atomicity — against exact-media fixtures:
media rows are prepared through the injected kernel ``media`` repository
(exact same-project kernel media ids the shot commands validate against),
and the prepared fixture bytes are materialized under the context's managed
root. The factories construct no ``DatabaseWriter`` and open no transaction
of their own: all mutation runs inside the caller's single ``BEGIN
IMMEDIATE`` unit of work, and the ``UnitOfWork`` uses inside
``prepare``/``seed`` are the caller-owned kernel currency the kit's own
checks drive.

``prepare`` is project-idempotent for the media imports (fixed per-project
idempotency keys) so the five kit checks that each call ``prepare`` on the
same database never collide with the kernel media vertical's project-scoped
byte dedupe; the per-check shot fixtures are key-derived and therefore
always distinct.

The factories depend only on the injected ``shots``, ``media``, and
``projects`` context repositories — never on the references pack — and the
references factories never touch ``shots``, so either pack's specs run
independently when the other pack repository is absent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from astrid.core.conformance.kit import (
    TS,
    CommandSpec,
    ConformanceContext,
    ConformanceError,
)
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.store.uow import UnitOfWork
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CREATE_COMMAND_KIND,
    SHOT_CREATED_EVENT_KIND,
    SHOT_ITEM_ADDED_EVENT_KIND,
    SHOT_ITEM_REMOVED_EVENT_KIND,
    SHOT_REMOVE_ITEM_COMMAND_KIND,
    SHOT_REORDER_COMMAND_KIND,
    SHOT_REORDERED_EVENT_KIND,
    SHOT_STREAM_TYPE,
)

TS2 = "2026-08-15T01:00:00.000000+00:00"
"""Second deterministic timestamp used by mutation commands."""

# ---------------------------------------------------------------------------
# Deterministic fixture facts
# ---------------------------------------------------------------------------

_MEDIA_FIXTURES: tuple[tuple[str, str, bytes], ...] = (
    (
        "a",
        "fixtures/shot-a.svg",
        b"<svg xmlns='http://www.w3.org/2000/svg'/>",
    ),
    (
        "b",
        "fixtures/shot-b.svg",
        b"<svg xmlns='http://www.w3.org/2000/svg' width='2'/>",
    ),
)
"""Two distinct prepared-file variants (distinct digests) the specs import."""

_SEED_KEYS: dict[str, str] = {
    "create": "crash-shot-create",
    "add_item": "crash-shot-add-item",
    "remove_item": "crash-shot-remove-item",
    "reorder": "crash-shot-reorder",
}
"""Fixed idempotency keys the crash-check seeds use (deterministic replay)."""


def _media_id(variant: str) -> str:
    """Deterministic kernel media id for one fixture variant."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"astrid-conformance-shot-media:{variant}"))


def _stable_shot_id(key: str, suffix: str = "") -> str:
    """Deterministic shot id for one kit key (stable-ID replay)."""
    namespace = (
        f"astrid-conformance-shot:{suffix}:{key}" if suffix else f"astrid-conformance-shot:{key}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, namespace))


def _stable_item_id(key: str, suffix: str = "") -> str:
    """Deterministic shot-item id for one kit key and position suffix."""
    namespace = (
        f"astrid-conformance-shot-item:{suffix}:{key}"
        if suffix
        else f"astrid-conformance-shot-item:{key}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, namespace))


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _require(ctx: ConformanceContext, name: str) -> Any:
    """Return one injected context repository or fail with a clear error."""
    value = getattr(ctx, name, None)
    if value is None:
        raise ConformanceError(f"shots conformance needs a context with {name!r} injected")
    return value


def _materialize_fixtures(context: ConformanceContext) -> None:
    """Write (idempotently) the prepared fixture files under the managed root."""
    root = context.managed_root
    if root is None:
        raise ConformanceError("shots conformance needs a context with a managed_root")
    for _variant, rel, payload in _MEDIA_FIXTURES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _import_media(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    variant: str,
    key: str,
) -> Any:
    """Import one fixture variant as exact kernel media inside *uow*."""
    media = _require(context, "media")
    if context.managed_root is None:
        raise ConformanceError("shots conformance needs a context with a managed_root")
    rel = dict((entry[0], entry[1]) for entry in _MEDIA_FIXTURES)[variant]
    prepared = prepare_media_file(context.managed_root / rel, root=context.managed_root)
    return media.import_prepared(
        uow,
        project_id=project_id,
        prepared=prepared,
        idempotency_key=key,
        media_id=_media_id(variant),
        created_at=TS,
    )


def _create_shot(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    shot_id: str,
    name: str,
    key: str,
) -> Any:
    """Create one empty shot inside *uow* (deterministic identity)."""
    shots = _require(context, "shots")
    return shots.create(
        uow,
        project_id=project_id,
        name=name,
        metadata={"conformance": key},
        idempotency_key=key,
        shot_id=shot_id,
        created_at=TS,
    )


def _add_prepared_item(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    shot_id: str,
    variant: str,
    item_id: str,
    key: str,
    position: int,
) -> Any:
    """Insert one exact-media item inside *uow* (deterministic identity)."""
    shots = _require(context, "shots")
    return shots.add_item(
        uow,
        project_id=project_id,
        shot_id=shot_id,
        media_id=_media_id(variant),
        position=position,
        source_frame=0,
        idempotency_key=key,
        item_id=item_id,
        created_at=TS,
    )


def _prepare_base(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
) -> None:
    """Import both media fixtures into *project_id* (project-idempotent).

    Called by every check's ``prepare`` on the same project; the fixed
    per-project idempotency keys make the second and later imports replay the
    stored media receipt with zero new rows, so the kernel media vertical's
    project-scoped byte dedupe never hits a duplicate-location conflict.
    """
    _materialize_fixtures(context)

    def _run(uow: UnitOfWork) -> None:
        _import_media(
            context,
            uow,
            project_id=project_id,
            variant="a",
            key=f"shot-conf-media-a-{project_id}",
        )
        _import_media(
            context,
            uow,
            project_id=project_id,
            variant="b",
            key=f"shot-conf-media-b-{project_id}",
        )

    UnitOfWork(writer).run(_run)


# ---------------------------------------------------------------------------
# shot.create
# ---------------------------------------------------------------------------


def _prepare_create(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """Create needs only the same-project media rows to target."""
    _prepare_base(context, writer, project_id=project_id)


def _invoke_create(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    return shots.create(
        uow,
        project_id=project_id,
        name=f"Shot {key}",
        metadata={"scene": key},
        idempotency_key=key,
        shot_id=_stable_shot_id(key),
        created_at=TS,
    )


def _invoke_create_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    return shots.create(
        uow,
        project_id=project_id,
        name=f"Changed Shot {key}",
        metadata={"scene": key},
        idempotency_key=key,
        shot_id=_stable_shot_id(key),
        created_at=TS,
    )


def _seed_create(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["create"]
    _materialize_fixtures(context)

    def _run(uow: UnitOfWork) -> None:
        context.projects.create(
            uow,
            slug="crash-proj",
            name="Crash Project",
            settings={},
            idempotency_key="crash-seed-project",
            project_id="crash-proj",
            created_at=TS,
        )
        _import_media(context, uow, project_id="crash-proj", variant="a", key=f"{key}-media-a")
        _import_media(context, uow, project_id="crash-proj", variant="b", key=f"{key}-media-b")

    UnitOfWork(writer).run(_run)
    return {"project_id": "crash-proj", "ref": None, "key": key}


# ---------------------------------------------------------------------------
# shot.add_item
# ---------------------------------------------------------------------------


def _prepare_add_item(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """add_item needs one empty shot plus the same-project media rows."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name=f"Prepared {key}",
            key=f"prepare-{key}-shot",
        )

    UnitOfWork(writer).run(_run)


def _invoke_add_item(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    return shots.add_item(
        uow,
        project_id=project_id,
        shot_id=_stable_shot_id(f"prepare-{key}"),
        media_id=_media_id("a"),
        position=0,
        source_frame=0,
        metadata={"tag": key},
        idempotency_key=key,
        item_id=_stable_item_id(key, "a"),
        created_at=TS2,
    )


def _invoke_add_item_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    # A different exact media id under the same key is a receipt mismatch
    # before any write (the receipt gate runs before the media fence).
    return shots.add_item(
        uow,
        project_id=project_id,
        shot_id=_stable_shot_id(f"prepare-{key}"),
        media_id=_media_id("b"),
        position=0,
        source_frame=0,
        metadata={"tag": key},
        idempotency_key=key,
        item_id=_stable_item_id(key, "a"),
        created_at=TS2,
    )


def _seed_add_item(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["add_item"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name="Crash Shot",
            key=f"{key}-shot",
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_shot_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# shot.remove_item
# ---------------------------------------------------------------------------


def _prepare_remove_item(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """remove_item needs a shot carrying exactly the item to remove."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name=f"Prepared {key}",
            key=f"prepare-{key}-shot",
        )
        _add_prepared_item(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="a",
            item_id=_stable_item_id(f"prepare-{key}", "a"),
            key=f"prepare-{key}-item-a",
            position=0,
        )

    UnitOfWork(writer).run(_run)


def _invoke_remove_item(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    return shots.remove_item(
        uow,
        project_id=project_id,
        shot_id=_stable_shot_id(f"prepare-{key}"),
        item_id=_stable_item_id(f"prepare-{key}", "a"),
        idempotency_key=key,
        created_at=TS2,
    )


def _invoke_remove_item_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    # A different item identity under the same key is a receipt mismatch
    # before any write (the receipt gate runs before the existence fence).
    return shots.remove_item(
        uow,
        project_id=project_id,
        shot_id=_stable_shot_id(f"prepare-{key}"),
        item_id=_stable_item_id(f"prepare-{key}", "b"),
        idempotency_key=key,
        created_at=TS2,
    )


def _seed_remove_item(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["remove_item"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name="Crash Shot",
            key=f"{key}-shot",
        )
        _add_prepared_item(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="a",
            item_id=_stable_item_id(f"prepare-{key}", "a"),
            key=f"{key}-item-a",
            position=0,
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_shot_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# shot.reorder
# ---------------------------------------------------------------------------


def _prepare_reorder(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """reorder needs a shot carrying two items in a known order."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name=f"Prepared {key}",
            key=f"prepare-{key}-shot",
        )
        _add_prepared_item(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="a",
            item_id=_stable_item_id(f"prepare-{key}", "a"),
            key=f"prepare-{key}-item-a",
            position=0,
        )
        _add_prepared_item(
            context,
            uow,
            project_id=project_id,
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="b",
            item_id=_stable_item_id(f"prepare-{key}", "b"),
            key=f"prepare-{key}-item-b",
            position=1,
        )

    UnitOfWork(writer).run(_run)


def _invoke_reorder(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    shot_id = _stable_shot_id(f"prepare-{key}")
    return shots.reorder(
        uow,
        project_id=project_id,
        shot_id=shot_id,
        item_ids=[
            _stable_item_id(f"prepare-{key}", "b"),
            _stable_item_id(f"prepare-{key}", "a"),
        ],
        idempotency_key=key,
        created_at=TS2,
    )


def _invoke_reorder_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    shots = _require(context, "shots")
    shot_id = _stable_shot_id(f"prepare-{key}")
    # The original order under the same key is a receipt mismatch before any
    # write (the receipt gate runs before the permutation fence).
    return shots.reorder(
        uow,
        project_id=project_id,
        shot_id=shot_id,
        item_ids=[
            _stable_item_id(f"prepare-{key}", "a"),
            _stable_item_id(f"prepare-{key}", "b"),
        ],
        idempotency_key=key,
        created_at=TS2,
    )


def _seed_reorder(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["reorder"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_shot(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            name="Crash Shot",
            key=f"{key}-shot",
        )
        _add_prepared_item(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="a",
            item_id=_stable_item_id(f"prepare-{key}", "a"),
            key=f"{key}-item-a",
            position=0,
        )
        _add_prepared_item(
            context,
            uow,
            project_id="crash-proj",
            shot_id=_stable_shot_id(f"prepare-{key}"),
            variant="b",
            item_id=_stable_item_id(f"prepare-{key}", "b"),
            key=f"{key}-item-b",
            position=1,
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_shot_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# Shared read/list adapters
# ---------------------------------------------------------------------------


def _shot_read(
    context: ConformanceContext,
    writer: Any,
    project_id: str,
    ref: str,
) -> Any:
    """Transaction-free show; a foreign project gets the typed not-found."""
    shots = _require(context, "shots")
    return shots.show(writer, project_id, ref)


def _shot_list_other(context: ConformanceContext, writer: Any, project_id: str) -> Any:
    """Another project's shot list (typed empty for the other project)."""
    shots = _require(context, "shots")
    return shots.list(writer, project_id)


def _shot_ref(model: Any) -> str:
    """Aggregate ref from a mutation result or the loaded read model."""
    return getattr(model, "shot_id", None) or model.id


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def shot_command_specs(
    context: ConformanceContext,
) -> dict[str, CommandSpec]:
    """Return the four pack-owned shot CommandSpec factories.

    Each spec is assembled from the injected context repositories (duck-typed
    ``shots``, ``media``, ``projects``), so the kernel kit never imports the
    pack. The returned mapping keys are exactly the frozen command kinds:
    ``shot.create``, ``shot.add_item``, ``shot.remove_item``, and
    ``shot.reorder``.
    """
    is_mismatch = lambda exc: isinstance(exc, ReceiptMismatchError)  # noqa: E731

    return {
        SHOT_CREATE_COMMAND_KIND: CommandSpec(
            command_kind=SHOT_CREATE_COMMAND_KIND,
            pack_id="shots",
            stream_type=SHOT_STREAM_TYPE,
            event_kinds=(SHOT_CREATED_EVENT_KIND,),
            invoke=_invoke_create,
            invoke_changed=_invoke_create_changed,
            read=_shot_read,
            seed=_seed_create,
            prepare=_prepare_create,
            is_expected_mismatch=is_mismatch,
            result_ref=_shot_ref,
            mutable_tables=("shots", "shot_items"),
            list_other=_shot_list_other,
        ),
        SHOT_ADD_ITEM_COMMAND_KIND: CommandSpec(
            command_kind=SHOT_ADD_ITEM_COMMAND_KIND,
            pack_id="shots",
            stream_type=SHOT_STREAM_TYPE,
            event_kinds=(SHOT_ITEM_ADDED_EVENT_KIND,),
            invoke=_invoke_add_item,
            invoke_changed=_invoke_add_item_changed,
            read=_shot_read,
            seed=_seed_add_item,
            prepare=_prepare_add_item,
            is_expected_mismatch=is_mismatch,
            result_ref=_shot_ref,
            mutable_tables=("shots", "shot_items"),
            list_other=_shot_list_other,
        ),
        SHOT_REMOVE_ITEM_COMMAND_KIND: CommandSpec(
            command_kind=SHOT_REMOVE_ITEM_COMMAND_KIND,
            pack_id="shots",
            stream_type=SHOT_STREAM_TYPE,
            event_kinds=(SHOT_ITEM_REMOVED_EVENT_KIND,),
            invoke=_invoke_remove_item,
            invoke_changed=_invoke_remove_item_changed,
            read=_shot_read,
            seed=_seed_remove_item,
            prepare=_prepare_remove_item,
            is_expected_mismatch=is_mismatch,
            result_ref=_shot_ref,
            mutable_tables=("shots", "shot_items"),
            list_other=_shot_list_other,
        ),
        SHOT_REORDER_COMMAND_KIND: CommandSpec(
            command_kind=SHOT_REORDER_COMMAND_KIND,
            pack_id="shots",
            stream_type=SHOT_STREAM_TYPE,
            event_kinds=(SHOT_REORDERED_EVENT_KIND,),
            invoke=_invoke_reorder,
            invoke_changed=_invoke_reorder_changed,
            read=_shot_read,
            seed=_seed_reorder,
            prepare=_prepare_reorder,
            is_expected_mismatch=is_mismatch,
            result_ref=_shot_ref,
            mutable_tables=("shots", "shot_items"),
            list_other=_shot_list_other,
        ),
    }


# Public command-spec surface; capability fixtures below are test-only data.
__all__ = ["shot_command_specs"]


@dataclass(frozen=True)
class CapabilityConformance:
    """One capability's representative conformance fixture."""

    capability_id: str
    family: str
    accepted_input: dict[str, Any]
    manifest: dict[str, Any]
    provenance: tuple[str, ...]
    invalid_input: dict[str, Any] | None = None
    child_only: bool = False


_TEMPLATE_PROVENANCE: tuple[str, ...] = (
    "family", "source_task_type", "output_policy", "params",
    "workflow.path", "workflow.sha256",
)
_BINDING_PROVENANCE: tuple[str, ...] = (
    "family", "source_task_type", "output_policy", "params",
)
_PROMPT = {"id": "p", "fullPrompt": "conformance"}


def manifest_census(workflow: dict[str, Any]) -> dict[str, Any]:
    """Derive completion-manifest expectations from graph bytes."""
    classes = [node.get("class_type") for node in workflow.values() if isinstance(node, dict)]
    images = sum(1 for c in classes if c == "SaveImage")
    videos = sum(1 for c in classes if isinstance(c, str) and c.startswith("VHS_VideoCombine"))
    return {"files": images + videos, "media": "image" if images else "video" if videos else "none"}


def _capability_fixtures() -> tuple[CapabilityConformance, ...]:
    """Fixtures for capabilities retained in the normal registry."""
    return (
        CapabilityConformance(
            "rendering.render", "render_export",
            {"timeline_ref": "tl-1", "expected_version": 0},
            {"files": 1, "media": "video"}, _BINDING_PROVENANCE, invalid_input={},
        ),
        CapabilityConformance(
            "rendering.timeline_visualize", "render_export",
            {"timeline_ref": "tl-1", "expected_version": 0},
            {"files": 0, "media": "none"}, _BINDING_PROVENANCE, invalid_input={},
        ),
        CapabilityConformance(
            "local.workflow.run", "local.workflow.run", {"id": "smoke_red"},
            {"files": 1, "media": "image"}, _TEMPLATE_PROVENANCE, invalid_input={},
        ),
    )


def capability_conformance_specs() -> tuple[CapabilityConformance, ...]:
    """Return the per-capability conformance fixtures (one per registry id)."""
    return _capability_fixtures()


__all__ = [
    "CapabilityConformance",
    "capability_conformance_specs",
    "manifest_census",
    "shot_command_specs",
]
