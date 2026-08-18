"""Pack-owned conformance CommandSpec factories for the references pack (m3 T13).

The references pack owns the executable command surface
(:class:`~astrid.packs.references.repository.ReferenceRepository`); this
module defines the five pack-owned :class:`~astrid.core.conformance.kit.CommandSpec`
factories — ``reference.create``, ``reference.archive``, ``reference.associate``,
``reference.set_primary``, and ``reference.link`` — that drive the kernel
conformance kit over the real repositories on the real kernel writer.

The architecture boundary stays clean: this module imports only kernel code
(the conformance kit, media import, receipts, UoW, and error vocabulary) and
its own pack — the kernel kit never imports a pack, so ``astrid/core`` stays
free of pack imports (m3 watch item; T16 lint).

Every spec exercises the seven kit dimensions — replay, mismatch-before-
mutation, same-project rejection, vocabulary, writer ownership, hash chains,
and statement-boundary crash atomicity. Media rows are prepared through the
injected kernel ``media`` repository (exact same-project kernel media ids the
reference commands validate against), and the prepared fixture bytes are
materialized under the context's managed root. The factories construct no
``DatabaseWriter`` and open no transaction of their own: all mutation runs
inside the caller's single ``BEGIN IMMEDIATE`` unit of work, and the
``UnitOfWork`` uses in ``prepare``/``seed`` are the caller-owned kernel
currency the kit's own checks drive.

``prepare`` is project-idempotent for the media imports (fixed per-project
idempotency keys) so the five kit checks that each call ``prepare`` on the
same database never collide with the kernel media vertical's project-scoped
byte dedupe; the per-check reference fixtures are key-derived and therefore
always distinct.
"""

from __future__ import annotations

import uuid
from typing import Any

from astrid.core.conformance.kit import (
    CommandSpec,
    ConformanceContext,
    ConformanceError,
    TS,
)
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError
from astrid.core.store.uow import UnitOfWork
from astrid.packs.references.repository import (
    REFERENCE_ARCHIVE_COMMAND_KIND,
    REFERENCE_ARCHIVED_EVENT_KIND,
    REFERENCE_ASSOCIATE_COMMAND_KIND,
    REFERENCE_CREATE_COMMAND_KIND,
    REFERENCE_CREATED_EVENT_KIND,
    REFERENCE_LINK_COMMAND_KIND,
    REFERENCE_LINKED_EVENT_KIND,
    REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,
    REFERENCE_PRIMARY_CHANGED_EVENT_KIND,
    REFERENCE_SET_PRIMARY_COMMAND_KIND,
    REFERENCE_STREAM_TYPE,
    REFERENCE_SYMMETRIC_LINK_KIND,
)

TS2 = "2026-08-15T01:00:00.000000+00:00"
"""Second deterministic timestamp used by mutation commands."""

# ---------------------------------------------------------------------------
# Deterministic fixture facts
# ---------------------------------------------------------------------------

_MEDIA_FIXTURES: tuple[tuple[str, str, bytes], ...] = (
    (
        "a",
        "fixtures/reference-a.svg",
        b"<svg xmlns='http://www.w3.org/2000/svg'/>",
    ),
    (
        "b",
        "fixtures/reference-b.svg",
        b"<svg xmlns='http://www.w3.org/2000/svg' width='2'/>",
    ),
)
"""Two distinct prepared-file variants (distinct digests) the specs import."""

_SEED_KEYS: dict[str, str] = {
    "create": "crash-reference-create",
    "archive": "crash-reference-archive",
    "associate": "crash-reference-associate",
    "set_primary": "crash-reference-set-primary",
    "link": "crash-reference-link",
}
"""Fixed idempotency keys the crash-check seeds use (deterministic replay)."""


def _media_id(variant: str) -> str:
    """Deterministic kernel media id for one fixture variant."""
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, f"astrid-conformance-reference-media:{variant}"
        )
    )


def _stable_reference_id(key: str, suffix: str = "") -> str:
    """Deterministic reference id for one kit key (stable-ID replay)."""
    namespace = (
        f"astrid-conformance-reference:{suffix}:{key}"
        if suffix
        else f"astrid-conformance-reference:{key}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, namespace))


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _require(ctx: ConformanceContext, name: str) -> Any:
    """Return one injected context repository or fail with a clear error."""
    value = getattr(ctx, name, None)
    if value is None:
        raise ConformanceError(
            f"references conformance needs a context with {name!r} injected"
        )
    return value


def _materialize_fixtures(context: ConformanceContext) -> None:
    """Write (idempotently) the prepared fixture files under the managed root."""
    root = context.managed_root
    if root is None:
        raise ConformanceError(
            "references conformance needs a context with a managed_root"
        )
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
        raise ConformanceError(
            "references conformance needs a context with a managed_root"
        )
    rel = dict((entry[0], entry[1]) for entry in _MEDIA_FIXTURES)[variant]
    prepared = prepare_media_file(
        context.managed_root / rel, root=context.managed_root
    )
    return media.import_prepared(
        uow,
        project_id=project_id,
        prepared=prepared,
        idempotency_key=key,
        media_id=_media_id(variant),
        created_at=TS,
    )


def _create_reference(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    reference_id: str,
    kind: str,
    name: str,
    media_id: str,
    key: str,
) -> Any:
    """Create one active reference inside *uow* (deterministic identity)."""
    refs = _require(context, "references")
    return refs.create(
        uow,
        project_id=project_id,
        kind=kind,
        name=name,
        media_id=media_id,
        idempotency_key=key,
        reference_id=reference_id,
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
            key=f"ref-conf-media-a-{project_id}",
        )
        _import_media(
            context,
            uow,
            project_id=project_id,
            variant="b",
            key=f"ref-conf-media-b-{project_id}",
        )

    UnitOfWork(writer).run(_run)


# ---------------------------------------------------------------------------
# reference.create
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
    refs = _require(context, "references")
    return refs.create(
        uow,
        project_id=project_id,
        kind="character",
        name=f"Ref {key}",
        media_id=_media_id("a"),
        idempotency_key=key,
        reference_id=_stable_reference_id(key),
        created_at=TS,
    )


def _invoke_create_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.create(
        uow,
        project_id=project_id,
        kind="place",
        name=f"Ref {key}",
        media_id=_media_id("a"),
        idempotency_key=key,
        reference_id=_stable_reference_id(key),
        created_at=TS,
    )


def _seed_create(
    context: ConformanceContext, writer: Any
) -> dict[str, Any]:
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
        _import_media(
            context, uow, project_id="crash-proj", variant="a", key=f"{key}-media-a"
        )
        _import_media(
            context, uow, project_id="crash-proj", variant="b", key=f"{key}-media-b"
        )

    UnitOfWork(writer).run(_run)
    return {"project_id": "crash-proj", "ref": None, "key": key}


# ---------------------------------------------------------------------------
# reference.archive
# ---------------------------------------------------------------------------


def _prepare_archive(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """Archive needs one active reference (with its primary media) to target."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name=f"Prepared {key}",
            media_id=_media_id("a"),
            key=f"prepare-{key}-ref-a",
        )

    UnitOfWork(writer).run(_run)


def _invoke_archive(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.archive(
        uow,
        project_id=project_id,
        reference_id=_stable_reference_id(f"prepare-{key}"),
        idempotency_key=key,
        now=TS2,
    )


def _invoke_archive_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    # A different target under the same key is a receipt mismatch before any
    # write (the receipt gate runs before the existence fence).
    return refs.archive(
        uow,
        project_id=project_id,
        reference_id=_stable_reference_id(f"prepare-{key}", "other"),
        idempotency_key=key,
        now=TS2,
    )


def _seed_archive(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["archive"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name="Crash Ref",
            media_id=_media_id("a"),
            key=f"{key}-ref-a",
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_reference_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# reference.associate
# ---------------------------------------------------------------------------


def _prepare_associate(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """Associate needs an active reference plus a second same-project media."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name=f"Prepared {key}",
            media_id=_media_id("a"),
            key=f"prepare-{key}-ref-a",
        )

    UnitOfWork(writer).run(_run)


def _invoke_associate(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.associate(
        uow,
        project_id=project_id,
        reference_id=_stable_reference_id(f"prepare-{key}"),
        media_id=_media_id("b"),
        role="depicts",
        idempotency_key=key,
        created_at=TS2,
    )


def _invoke_associate_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.associate(
        uow,
        project_id=project_id,
        reference_id=_stable_reference_id(f"prepare-{key}"),
        media_id=_media_id("b"),
        role="inspired_by",
        idempotency_key=key,
        created_at=TS2,
    )


def _seed_associate(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["associate"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name="Crash Ref",
            media_id=_media_id("a"),
            key=f"{key}-ref-a",
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_reference_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# reference.set_primary
# ---------------------------------------------------------------------------


def _prepare_set_primary(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """set_primary needs a reference with two canonical associations."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name=f"Prepared {key}",
            media_id=_media_id("a"),
            key=f"prepare-{key}-ref-a",
        )
        refs = _require(context, "references")
        refs.associate(
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}"),
            media_id=_media_id("b"),
            role="canonical",
            idempotency_key=f"prepare-{key}-assoc-canonical",
            created_at=TS,
        )

    UnitOfWork(writer).run(_run)


def _canonical_association_id(
    uow: UnitOfWork, *, reference_id: str, media_id: str
) -> str:
    """Resolve the deterministic canonical association id for one media."""
    row = uow.query_one(
        "SELECT id FROM media_references "
        "WHERE reference_id = ? AND media_id = ? AND role = 'canonical'",
        (reference_id, media_id),
    )
    if row is None:
        raise ConformanceError(
            f"set_primary conformance: canonical media {media_id!r} "
            f"is not associated with reference {reference_id!r}"
        )
    return str(row["id"])


def _invoke_set_primary(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    reference_id = _stable_reference_id(f"prepare-{key}")
    return refs.set_primary(
        uow,
        project_id=project_id,
        reference_id=reference_id,
        media_reference_id=_canonical_association_id(
            uow, reference_id=reference_id, media_id=_media_id("b")
        ),
        idempotency_key=key,
        now=TS2,
    )


def _invoke_set_primary_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    reference_id = _stable_reference_id(f"prepare-{key}")
    return refs.set_primary(
        uow,
        project_id=project_id,
        reference_id=reference_id,
        media_reference_id=_canonical_association_id(
            uow, reference_id=reference_id, media_id=_media_id("a")
        ),
        idempotency_key=key,
        now=TS2,
    )


def _seed_set_primary(
    context: ConformanceContext, writer: Any
) -> dict[str, Any]:
    key = _SEED_KEYS["set_primary"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name="Crash Ref",
            media_id=_media_id("a"),
            key=f"{key}-ref-a",
        )
        refs = _require(context, "references")
        refs.associate(
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}"),
            media_id=_media_id("b"),
            role="canonical",
            idempotency_key=f"{key}-assoc-canonical",
            created_at=TS,
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_reference_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# reference.link
# ---------------------------------------------------------------------------


def _prepare_link(
    context: ConformanceContext,
    writer: Any,
    *,
    project_id: str,
    key: str,
) -> None:
    """Link needs two active references (each with its primary media)."""
    _prepare_base(context, writer, project_id=project_id)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name=f"Prepared {key}",
            media_id=_media_id("a"),
            key=f"prepare-{key}-ref-a",
        )
        _create_reference(
            context,
            uow,
            project_id=project_id,
            reference_id=_stable_reference_id(f"prepare-{key}", "q"),
            kind="place",
            name=f"Prepared {key} B",
            media_id=_media_id("b"),
            key=f"prepare-{key}-ref-b",
        )

    UnitOfWork(writer).run(_run)


def _invoke_link(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.link(
        uow,
        project_id=project_id,
        from_reference_id=_stable_reference_id(f"prepare-{key}"),
        to_reference_id=_stable_reference_id(f"prepare-{key}", "q"),
        kind=REFERENCE_SYMMETRIC_LINK_KIND,
        metadata={"scene": key},
        idempotency_key=key,
        created_at=TS2,
    )


def _invoke_link_changed(
    context: ConformanceContext,
    uow: UnitOfWork,
    *,
    project_id: str,
    key: str,
) -> Any:
    refs = _require(context, "references")
    return refs.link(
        uow,
        project_id=project_id,
        from_reference_id=_stable_reference_id(f"prepare-{key}"),
        to_reference_id=_stable_reference_id(f"prepare-{key}", "q"),
        kind="associated_with",
        metadata={"scene": key},
        idempotency_key=key,
        created_at=TS2,
    )


def _seed_link(context: ConformanceContext, writer: Any) -> dict[str, Any]:
    key = _SEED_KEYS["link"]
    _seed_create(context, writer)

    def _run(uow: UnitOfWork) -> None:
        _create_reference(
            context,
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}"),
            kind="character",
            name="Crash From",
            media_id=_media_id("a"),
            key=f"{key}-ref-a",
        )
        _create_reference(
            context,
            uow,
            project_id="crash-proj",
            reference_id=_stable_reference_id(f"prepare-{key}", "q"),
            kind="place",
            name="Crash To",
            media_id=_media_id("b"),
            key=f"{key}-ref-b",
        )

    UnitOfWork(writer).run(_run)
    return {
        "project_id": "crash-proj",
        "ref": _stable_reference_id(f"prepare-{key}"),
        "key": key,
    }


# ---------------------------------------------------------------------------
# Shared read/list adapters
# ---------------------------------------------------------------------------


def _reference_read(
    context: ConformanceContext,
    writer: Any,
    project_id: str,
    ref: str,
) -> Any:
    """Direct historical lookup; a foreign project gets the typed not-found."""
    refs = _require(context, "references")
    return refs.show(writer, project_id, ref)


def _reference_list_other(
    context: ConformanceContext, writer: Any, project_id: str
) -> Any:
    """Another project's reference list (typed empty for the other project)."""
    refs = _require(context, "references")
    return refs.list(writer, project_id)


def _reference_id_ref(model: Any) -> str:
    """Aggregate ref from a mutation result or the loaded read model."""
    return getattr(model, "reference_id", None) or model.id


def _link_ref(model: Any) -> str:
    """Aggregate ref from a link result (from-side) or the read model."""
    return getattr(model, "from_reference_id", None) or model.id


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def reference_command_specs(
    context: ConformanceContext,
) -> dict[str, CommandSpec]:
    """Return the five pack-owned reference CommandSpec factories.

    Each spec is assembled from the injected context repositories (duck-typed
    ``references``, ``media``, ``projects``), so the kernel kit never imports
    the pack. The returned mapping keys are exactly the frozen command kinds:
    ``reference.create``, ``reference.archive``, ``reference.associate``,
    ``reference.set_primary``, and ``reference.link``.
    """
    is_mismatch = lambda exc: isinstance(exc, ReceiptMismatchError)  # noqa: E731

    return {
        REFERENCE_CREATE_COMMAND_KIND: CommandSpec(
            command_kind=REFERENCE_CREATE_COMMAND_KIND,
            pack_id="references",
            stream_type=REFERENCE_STREAM_TYPE,
            event_kinds=(REFERENCE_CREATED_EVENT_KIND,),
            invoke=_invoke_create,
            invoke_changed=_invoke_create_changed,
            read=_reference_read,
            seed=_seed_create,
            prepare=_prepare_create,
            is_expected_mismatch=is_mismatch,
            result_ref=lambda model: model.id,
            mutable_tables=("project_references", "media_references"),
            list_other=_reference_list_other,
        ),
        REFERENCE_ARCHIVE_COMMAND_KIND: CommandSpec(
            command_kind=REFERENCE_ARCHIVE_COMMAND_KIND,
            pack_id="references",
            stream_type=REFERENCE_STREAM_TYPE,
            event_kinds=(REFERENCE_ARCHIVED_EVENT_KIND,),
            invoke=_invoke_archive,
            invoke_changed=_invoke_archive_changed,
            read=_reference_read,
            seed=_seed_archive,
            prepare=_prepare_archive,
            is_expected_mismatch=is_mismatch,
            result_ref=_reference_id_ref,
            mutable_tables=("project_references",),
            list_other=_reference_list_other,
        ),
        REFERENCE_ASSOCIATE_COMMAND_KIND: CommandSpec(
            command_kind=REFERENCE_ASSOCIATE_COMMAND_KIND,
            pack_id="references",
            stream_type=REFERENCE_STREAM_TYPE,
            event_kinds=(REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,),
            invoke=_invoke_associate,
            invoke_changed=_invoke_associate_changed,
            read=_reference_read,
            seed=_seed_associate,
            prepare=_prepare_associate,
            is_expected_mismatch=is_mismatch,
            result_ref=_reference_id_ref,
            mutable_tables=("project_references", "media_references"),
            list_other=_reference_list_other,
        ),
        REFERENCE_SET_PRIMARY_COMMAND_KIND: CommandSpec(
            command_kind=REFERENCE_SET_PRIMARY_COMMAND_KIND,
            pack_id="references",
            stream_type=REFERENCE_STREAM_TYPE,
            event_kinds=(REFERENCE_PRIMARY_CHANGED_EVENT_KIND,),
            invoke=_invoke_set_primary,
            invoke_changed=_invoke_set_primary_changed,
            read=_reference_read,
            seed=_seed_set_primary,
            prepare=_prepare_set_primary,
            is_expected_mismatch=is_mismatch,
            result_ref=_reference_id_ref,
            mutable_tables=("project_references", "media_references"),
            list_other=_reference_list_other,
        ),
        REFERENCE_LINK_COMMAND_KIND: CommandSpec(
            command_kind=REFERENCE_LINK_COMMAND_KIND,
            pack_id="references",
            stream_type=REFERENCE_STREAM_TYPE,
            event_kinds=(REFERENCE_LINKED_EVENT_KIND,),
            invoke=_invoke_link,
            invoke_changed=_invoke_link_changed,
            read=_reference_read,
            seed=_seed_link,
            prepare=_prepare_link,
            is_expected_mismatch=is_mismatch,
            result_ref=_link_ref,
            mutable_tables=("reference_links",),
            list_other=_reference_list_other,
        ),
    }


__all__ = ["reference_command_specs"]
