"""Shot-owned immutable text bindings.

The binding is deliberately a small projection: its current media pointer is
authoritative, while the existing ``shot.text_binding`` event stream is its
history and CAS version.  Media is always read through the injected Core
``MediaRepository`` so ownership and byte verification happen on the active
unit of work.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.events.service import ACTOR_KINDS, EventAppendService
from astrid.core.io.media_import import (
    PreparedMedia,
    managed_media_path,
    managed_root,
    validate_digest,
)
from astrid.core.receipts.canonical import canonical_json, request_hash
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.media import (
    MediaReadModel,
    MediaRepository,
)
from astrid.core.repositories.errors import RepositoryError
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.util.time import utc_now_iso

TEXT_BINDING_KINDS: tuple[str, ...] = (
    "prompt",
    "voiceover_script",
    "transcript",
)
"""The closed meaning vocabulary for shot-authored text."""

SHOT_TEXT_BINDING_STREAM_TYPE = "shot.text_binding"
SHOT_TEXT_BINDING_CREATED_EVENT_KIND = "shot.text_binding.created"
SHOT_TEXT_BINDING_REBOUND_EVENT_KIND = "shot.text_binding.rebound"
SHOT_TEXT_BINDING_SET_COMMAND_KIND = "shot.text_binding.set"
SHOT_TEXT_BINDING_REBIND_COMMAND_KIND = "shot.text_binding.rebind"
SHOT_TEXT_BINDING_APPLY_COMMAND_KIND = "shot.text_binding.apply"
TEXT_BINDING_IDENTITY_SCHEMA = "astrid.shot.text_binding.identity/v1"
MAX_SHOT_TEXT_BYTES = 1_048_576

_SLOT_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ShotTextBindingError(RepositoryError):
    """Base class for typed text-binding repository failures."""


class ShotTextBindingValidationError(ShotTextBindingError):
    """Caller input violates the binding contract."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(message)


class ShotTextBindingNotFoundError(ShotTextBindingError):
    """A binding or shot is absent from the requested project scope."""

    def __init__(self, *, binding_id: str | None = None, shot_id: str | None = None, project_id: str | None = None) -> None:
        self.binding_id = binding_id
        self.shot_id = shot_id
        self.project_id = project_id
        subject = binding_id or shot_id or "binding"
        super().__init__(f"unknown text binding target {subject!r}")


class ShotTextBindingAmbiguousError(ShotTextBindingError):
    """A friendly selector resolves to more than one candidate."""

    def __init__(self, *, candidates: Sequence[Mapping[str, Any]], subject: str = "text binding") -> None:
        self.candidates = tuple(dict(candidate) for candidate in candidates)
        super().__init__(f"ambiguous {subject} selector")


class ShotTextBindingConflictError(ShotTextBindingError):
    """A deterministic identity or media candidate conflicts with state."""

    def __init__(self, *, reason: str, binding_id: str | None = None) -> None:
        self.reason = reason
        self.binding_id = binding_id
        super().__init__(f"text binding conflict: {reason}")


class ShotTextBindingStaleError(ShotTextBindingError):
    """The binding stream head no longer matches the caller's expected head."""

    def __init__(self, *, expected_head: int, actual_head: int, binding_id: str) -> None:
        self.expected_head = expected_head
        self.actual_head = actual_head
        self.binding_id = binding_id
        super().__init__(
            f"text binding {binding_id!r} expected head {expected_head}, "
            f"current head is {actual_head}"
        )


class ShotTextBindingIntegrityError(ShotTextBindingError):
    """Persisted media or binding state failed the canonical verifier."""

    def __init__(self, *, detail: str, media_id: str | None = None) -> None:
        self.detail = detail
        self.media_id = media_id
        super().__init__(f"text binding media integrity failure: {detail}")


class ShotTextBindingMediaCandidateError(ShotTextBindingError):
    """A proposed reuse/rebind target has a frozen candidate failure."""

    def __init__(self, *, detail: str, media_id: str | None = None) -> None:
        self.detail = detail
        self.media_id = media_id
        super().__init__(f"text binding media candidate rejected: {detail}")


@dataclass(frozen=True, slots=True)
class ShotTextBinding:
    """Complete current binding projection plus its stream head."""

    binding_id: str
    project_id: str
    shot_id: str
    kind: str
    slot: str | None
    media_id: str
    event_stream_id: str
    head: int
    content_hash: str
    mime_type: str
    byte_size: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "project_id": self.project_id,
            "shot_id": self.shot_id,
            "kind": self.kind,
            "slot": self.slot,
            "media_id": self.media_id,
            "event_stream_id": self.event_stream_id,
            "head": self.head,
            "content_hash": self.content_hash,
            "mime_type": self.mime_type,
            "byte_size": self.byte_size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShotTextBinding":
        return cls(
            binding_id=str(value["binding_id"]),
            project_id=str(value["project_id"]),
            shot_id=str(value["shot_id"]),
            kind=str(value["kind"]),
            slot=value.get("slot"),
            media_id=str(value["media_id"]),
            event_stream_id=str(value["event_stream_id"]),
            head=int(value["head"]),
            content_hash=str(value["content_hash"]),
            mime_type=str(value["mime_type"]),
            byte_size=int(value["byte_size"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )


@dataclass(frozen=True, slots=True)
class ShotTextBindingMutation:
    """Mutation result; ``changed`` is outside the binding read model."""

    changed: bool
    binding: ShotTextBinding

    def to_dict(self) -> dict[str, Any]:
        return {"changed": self.changed, "binding": self.binding.to_dict()}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShotTextBindingMutation":
        return cls(
            changed=bool(value["changed"]),
            binding=ShotTextBinding.from_mapping(value["binding"]),
        )


@dataclass(frozen=True, slots=True)
class FrozenTextBytes:
    """Caller bytes admitted before the writer transaction."""

    value: bytes
    byte_size: int
    digest: str


@dataclass(frozen=True, slots=True)
class _VerifiedMedia:
    media: MediaReadModel
    path: Path
    size: int
    mtime_ns: int
    digest: str


@dataclass(frozen=True, slots=True)
class _MutationOutcome:
    """Internal changed-command facts needed for one encompassing receipt."""

    mutation: ShotTextBindingMutation
    event_ids: tuple[str, ...]
    project_seqs: tuple[int, ...]
    txn_id: str


def validate_text_binding_kind(kind: object) -> str:
    if not isinstance(kind, str) or kind not in TEXT_BINDING_KINDS:
        raise ShotTextBindingValidationError(
            f"kind must be one of {TEXT_BINDING_KINDS}", detail="kind"
        )
    return kind


def validate_text_binding_slot(slot: object, *, kind: str) -> str | None:
    if slot is None:
        return None
    if not isinstance(slot, str) or _SLOT_RE.fullmatch(slot) is None:
        raise ShotTextBindingValidationError(
            "slot must be a lowercase slug of 1-64 characters", detail="slot"
        )
    if kind != "prompt":
        raise ShotTextBindingValidationError(
            "slot is allowed only for prompt bindings", detail="slot_kind"
        )
    return slot


def derive_text_binding_id(
    *, project_id: str, shot_id: str, kind: str, slot: str | None
) -> str:
    """Derive the natural binding identity without an idempotency key."""
    validate_text_binding_kind(kind)
    slot = validate_text_binding_slot(slot, kind=kind)
    identity = {
        "schema": TEXT_BINDING_IDENTITY_SCHEMA,
        "project_id": project_id,
        "shot_id": shot_id,
        "kind": kind,
        "slot": slot,
    }
    return str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_json(identity)))


def derive_text_binding_stream_id(binding_id: str) -> str:
    if not isinstance(binding_id, str) or not binding_id:
        raise ShotTextBindingValidationError("binding_id must be a non-empty string")
    return f"{binding_id}:{SHOT_TEXT_BINDING_STREAM_TYPE}"


def freeze_text_bytes(value: bytes) -> FrozenTextBytes:
    """Bound, copy, decode, and digest caller bytes before SQL begins."""
    if not isinstance(value, bytes):
        raise ShotTextBindingValidationError("text must be bytes", detail="text")
    frozen = bytes(value)
    if len(frozen) > MAX_SHOT_TEXT_BYTES:
        raise ShotTextBindingValidationError(
            f"text exceeds {MAX_SHOT_TEXT_BYTES} bytes", detail="too_large"
        )
    try:
        frozen.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ShotTextBindingValidationError(
            "text is not valid UTF-8", detail="invalid_utf8"
        ) from exc
    return FrozenTextBytes(
        value=frozen,
        byte_size=len(frozen),
        digest=hashlib.sha256(frozen).hexdigest(),
    )


def _require_project(project_id: object) -> str:
    if not isinstance(project_id, str) or not project_id:
        raise ShotTextBindingValidationError("project_id must be a non-empty string")
    return project_id


def _require_key(key: object) -> str:
    if not isinstance(key, str) or not key:
        raise ShotTextBindingValidationError("idempotency_key must be a non-empty string")
    return key


def _require_head(head: object) -> int:
    if isinstance(head, bool) or not isinstance(head, int) or head < 0:
        raise ShotTextBindingValidationError(
            "expected_head must be a non-negative integer", detail="expected_head"
        )
    return head


class ShotTextBindingRepository:
    """Focused Shots-pack repository for binding projection and commands."""

    def __init__(
        self,
        events: EventAppendService,
        receipts: ReceiptService,
        media: MediaRepository | None = None,
        projects_root: str | Path | None = None,
    ) -> None:
        self._events = events
        self._receipts = receipts
        self._media = media
        self._projects_root = Path(projects_root) if projects_root is not None else None

    # -- selectors -------------------------------------------------------

    @staticmethod
    def _resolve_shot(uow: UnitOfWork, project_id: str, shot_ref: str) -> Any:
        if not isinstance(shot_ref, str) or not shot_ref:
            raise ShotTextBindingValidationError("shot_ref must be a non-empty string")
        row = uow.query_one(
            "SELECT id, name, sort_key FROM shots WHERE id = ? AND project_id = ?",
            (shot_ref, project_id),
        )
        if row is not None:
            return row
        row = uow.query_one(
            "SELECT id, name, sort_key FROM shots WHERE sort_key = ? AND project_id = ?",
            (shot_ref, project_id),
        )
        if row is not None:
            return row
        rows = uow.query(
            "SELECT id, name, sort_key FROM shots WHERE name = ? AND project_id = ? "
            "ORDER BY id ASC",
            (shot_ref, project_id),
        )
        if not rows:
            raise ShotTextBindingNotFoundError(shot_id=shot_ref, project_id=project_id)
        if len(rows) > 1:
            raise ShotTextBindingAmbiguousError(
                candidates=[
                    {"id": str(row["id"]), "name": str(row["name"]), "sort_key": str(row["sort_key"])}
                    for row in rows
                ],
                subject="shot",
            )
        return rows[0]

    def _resolve_binding(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        binding_id: str | None = None,
        shot_ref: str | None = None,
        kind: str | None = None,
        slot: str | None = None,
        creation: bool = False,
    ) -> Any:
        if binding_id is not None:
            if shot_ref is not None or kind is not None or slot is not None:
                raise ShotTextBindingValidationError(
                    "binding_id cannot be combined with friendly selectors"
                )
            row = uow.query_one(
                "SELECT * FROM shot_text_bindings WHERE id = ? AND project_id = ?",
                (binding_id, project_id),
            )
            if row is None:
                raise ShotTextBindingNotFoundError(binding_id=binding_id, project_id=project_id)
            return row
        if shot_ref is None or kind is None:
            raise ShotTextBindingValidationError(
                "friendly selector requires shot_ref and kind"
            )
        kind = validate_text_binding_kind(kind)
        if slot is not None:
            validate_text_binding_slot(slot, kind=kind)
        shot = ShotTextBindingRepository._resolve_shot(uow, project_id, shot_ref)
        params: list[object] = [project_id, str(shot["id"]), kind]
        sql = (
            "SELECT * FROM shot_text_bindings WHERE project_id = ? "
            "AND shot_id = ? AND kind = ?"
        )
        if slot is not None:
            sql += " AND slot = ?"
            params.append(slot)
        elif creation:
            sql += " AND slot IS NULL"
        else:
            # Existing-target omission is a wildcard, including all prompt
            # slots; an ambiguous result is intentionally not guessed.
            pass
        sql += " ORDER BY slot IS NOT NULL ASC, slot ASC, id ASC"
        rows = uow.query(sql, tuple(params))
        if not rows:
            raise ShotTextBindingNotFoundError(
                shot_id=str(shot["id"]), project_id=project_id
            )
        if len(rows) > 1:
            raise ShotTextBindingAmbiguousError(
                candidates=[self._candidate(uow, dict(row), project_id) for row in rows]
            )
        return rows[0]

    def _candidate(
        self, uow: UnitOfWork, row: Mapping[str, Any], project_id: str
    ) -> dict[str, Any]:
        row = dict(row)
        media = (
            self._media.read_project_media(
                uow, project_id=project_id, media_id=str(row["media_id"])
            )
            if self._media is not None
            else None
        )
        stream = uow.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
            (row["event_stream_id"], project_id),
        )
        return {
            "binding_id": str(row["id"]),
            "media_id": str(row["media_id"]),
            "content_hash": media.content_hash if media is not None else "",
            "head": int(stream["head_seq"]) if stream is not None else 0,
            "slot": row.get("slot"),
        }

    def _binding_row(self, uow: UnitOfWork, row: Mapping[str, Any]) -> ShotTextBinding:
        if self._media is None:
            raise ShotTextBindingValidationError("a Core MediaRepository is required")
        stream = uow.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
            (row["event_stream_id"], row["project_id"]),
        )
        if stream is None:
            raise ShotTextBindingIntegrityError(detail="binding_stream_missing")
        media = self._media.read_project_media(
            uow, project_id=str(row["project_id"]), media_id=str(row["media_id"])
        )
        if media is None:
            raise ShotTextBindingIntegrityError(
                detail="bound_media_missing", media_id=str(row["media_id"])
            )
        verified = self._verify_managed_text(media, current=True)
        self._verify_fingerprint(verified)
        return ShotTextBinding(
            binding_id=str(row["id"]),
            project_id=str(row["project_id"]),
            shot_id=str(row["shot_id"]),
            kind=str(row["kind"]),
            slot=row["slot"],
            media_id=media.id,
            event_stream_id=str(row["event_stream_id"]),
            head=int(stream["head_seq"]),
            content_hash=media.content_hash,
            mime_type=media.mime_type,
            byte_size=media.byte_size,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def show(
        self,
        writer: DatabaseWriter,
        *,
        project_id: str,
        binding_id: str,
    ) -> ShotTextBinding:
        """Read and canonically verify one project-scoped binding."""
        project_id = _require_project(project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM shot_text_bindings WHERE id = ? AND project_id = ?",
                (binding_id, project_id),
            ).fetchone()
            if row is None:
                raise ShotTextBindingNotFoundError(binding_id=binding_id, project_id=project_id)
            # ``read_project_media`` accepts a connection, so this read stays
            # on the same read-only snapshot as the binding row.
            if self._media is None:
                raise ShotTextBindingValidationError("a Core MediaRepository is required")
            media = self._media.read_project_media(
                conn, project_id=project_id, media_id=str(row["media_id"])
            )
            if media is None:
                raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=str(row["media_id"]))
            verified = self._verify_managed_text(media, current=True)
            self._verify_fingerprint(verified)
            stream = conn.execute(
                "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
                (row["event_stream_id"], project_id),
            ).fetchone()
            if stream is None:
                raise ShotTextBindingIntegrityError(detail="binding_stream_missing")
            return ShotTextBinding(
                binding_id=str(row["id"]), project_id=project_id,
                shot_id=str(row["shot_id"]), kind=str(row["kind"]), slot=row["slot"],
                media_id=media.id, event_stream_id=str(row["event_stream_id"]),
                head=int(stream["head_seq"]), content_hash=media.content_hash,
                mime_type=media.mime_type, byte_size=media.byte_size,
                created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
            )

    def list(
        self,
        writer: DatabaseWriter,
        *,
        project_id: str,
        shot_ref: str | None = None,
        kind: str | None = None,
        slot: str | None = None,
    ) -> list[ShotTextBinding]:
        """List bindings with optional project-scoped friendly narrowing."""
        project_id = _require_project(project_id)
        with writer.read_only_connection() as conn:
            conn.row_factory = sqlite3.Row
            params: list[object] = []
            sql = "SELECT b.* FROM shot_text_bindings b"
            if shot_ref is not None:
                shot = conn.execute(
                    "SELECT id FROM shots WHERE id = ? AND project_id = ?",
                    (shot_ref, project_id),
                ).fetchone()
                if shot is None:
                    shot = conn.execute(
                        "SELECT id FROM shots WHERE sort_key = ? AND project_id = ?",
                        (shot_ref, project_id),
                    ).fetchone()
                if shot is None:
                    shots = conn.execute(
                        "SELECT id, name, sort_key FROM shots WHERE name = ? AND project_id = ? ORDER BY id ASC",
                        (shot_ref, project_id),
                    ).fetchall()
                    if not shots:
                        raise ShotTextBindingNotFoundError(shot_id=shot_ref, project_id=project_id)
                    if len(shots) > 1:
                        raise ShotTextBindingAmbiguousError(
                            candidates=[dict(row) for row in shots], subject="shot"
                        )
                    shot = shots[0]
                sql += " JOIN shots s ON s.id = b.shot_id AND s.project_id = ? AND s.id = ?"
                params.extend([project_id, str(shot["id"])])
            else:
                sql += " JOIN shots s ON s.id = b.shot_id AND s.project_id = ?"
                params.append(project_id)
            sql += " WHERE b.project_id = ?"
            params.append(project_id)
            if kind is not None:
                kind = validate_text_binding_kind(kind)
                sql += " AND b.kind = ?"
                params.append(kind)
            if slot is not None:
                if kind is None:
                    raise ShotTextBindingValidationError("slot requires kind=prompt")
                validate_text_binding_slot(slot, kind=kind)
                sql += " AND b.slot = ?"
                params.append(slot)
            sql += " ORDER BY b.id ASC"
            rows = conn.execute(sql, tuple(params)).fetchall()
            result: list[ShotTextBinding] = []
            for row in rows:
                media = self._media.read_project_media(
                    conn, project_id=project_id, media_id=str(row["media_id"])
                ) if self._media is not None else None
                if media is None:
                    raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=str(row["media_id"]))
                verified = self._verify_managed_text(media, current=True)
                self._verify_fingerprint(verified)
                stream = conn.execute(
                    "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
                    (row["event_stream_id"], project_id),
                ).fetchone()
                if stream is None:
                    raise ShotTextBindingIntegrityError(detail="binding_stream_missing")
                result.append(ShotTextBinding(
                    binding_id=str(row["id"]), project_id=project_id,
                    shot_id=str(row["shot_id"]), kind=str(row["kind"]), slot=row["slot"],
                    media_id=media.id, event_stream_id=str(row["event_stream_id"]),
                    head=int(stream["head_seq"]), content_hash=media.content_hash,
                    mime_type=media.mime_type, byte_size=media.byte_size,
                    created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
                ))
            return result

    def resolve(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        binding_id: str | None = None,
        shot_ref: str | None = None,
        kind: str | None = None,
        slot: str | None = None,
        creation: bool = False,
    ) -> ShotTextBinding:
        """Resolve an exact or friendly target inside the active UoW."""
        row = self._resolve_binding(
            uow,
            project_id=_require_project(project_id),
            binding_id=binding_id,
            shot_ref=shot_ref,
            kind=kind,
            slot=slot,
            creation=creation,
        )
        return self._binding_row(uow, row)

    # -- canonical persisted media verifier -----------------------------

    def _verify_managed_text(self, media: MediaReadModel, *, current: bool) -> _VerifiedMedia:
        if media.media_kind != "text":
            detail = "content_hash_media_kind_collision"
            if current:
                raise ShotTextBindingIntegrityError(detail=detail, media_id=media.id)
            raise ShotTextBindingMediaCandidateError(detail=detail, media_id=media.id)
        managed_locations = [location for location in media.locations if location.realm == "managed_local"]
        if len(managed_locations) == 0:
            if current:
                raise ShotTextBindingIntegrityError(detail="managed_local_missing", media_id=media.id)
            raise ShotTextBindingMediaCandidateError(detail="managed_local_required", media_id=media.id)
        if len(managed_locations) > 1:
            raise ShotTextBindingConflictError(reason="multiple_managed_locations", binding_id=media.id)
        locator = Path(managed_locations[0].locator)
        projects_root = self._projects_root
        if projects_root is None and self._media is not None:
            projects_root = Path(getattr(self._media, "_projects_root"))
        if projects_root is None:
            raise ShotTextBindingValidationError(
                "projects_root is required for media verification"
            )
        root = managed_root(projects_root)
        expected = managed_media_path(projects_root, media.content_hash)
        try:
            resolved_locator = locator.resolve(strict=False)
            resolved_expected = expected.resolve(strict=False)
            resolved_root = root.resolve(strict=False)
        except OSError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_file_missing", media_id=media.id) from exc
        if resolved_locator != resolved_expected:
            raise ShotTextBindingIntegrityError(detail="managed_locator_mismatch", media_id=media.id)
        try:
            resolved_expected.relative_to(resolved_root)
        except ValueError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_locator_mismatch", media_id=media.id) from exc
        try:
            stat = os.lstat(resolved_expected)
        except OSError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_file_missing", media_id=media.id) from exc
        if os.path.islink(resolved_expected):
            raise ShotTextBindingIntegrityError(detail="managed_file_symlink", media_id=media.id)
        if not os.path.isfile(resolved_expected):
            raise ShotTextBindingIntegrityError(detail="managed_file_not_regular", media_id=media.id)
        try:
            data = resolved_expected.read_bytes()
        except OSError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_file_unreadable", media_id=media.id) from exc
        if len(data) != media.byte_size:
            raise ShotTextBindingIntegrityError(detail="managed_size_mismatch", media_id=media.id)
        digest = hashlib.sha256(data).hexdigest()
        if digest != media.content_hash:
            raise ShotTextBindingIntegrityError(detail="managed_hash_mismatch", media_id=media.id)
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_bytes_invalid_utf8", media_id=media.id) from exc
        return _VerifiedMedia(media=media, path=resolved_expected, size=len(data), mtime_ns=stat.st_mtime_ns, digest=digest)

    @staticmethod
    def _verify_fingerprint(verified: _VerifiedMedia) -> None:
        try:
            stat = os.lstat(verified.path)
            data = verified.path.read_bytes()
        except OSError as exc:
            raise ShotTextBindingIntegrityError(detail="managed_file_mutated", media_id=verified.media.id) from exc
        if (
            os.path.islink(verified.path)
            or stat.st_size != verified.size
            or stat.st_mtime_ns != verified.mtime_ns
            or hashlib.sha256(data).hexdigest() != verified.digest
        ):
            raise ShotTextBindingIntegrityError(detail="managed_file_mutated", media_id=verified.media.id)

    def _resolve_desired_media(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        desired_media_id: str | None = None,
        desired_digest: str | None = None,
        current: bool = False,
    ) -> MediaReadModel | None:
        if self._media is None:
            raise ShotTextBindingValidationError("a Core MediaRepository is required")
        if (desired_media_id is None) == (desired_digest is None):
            raise ShotTextBindingValidationError("exactly one desired media selector is required")
        media = self._media.read_project_media(
            uow,
            project_id=project_id,
            media_id=desired_media_id,
        ) if desired_media_id is not None else self._media.read_project_media(
            uow,
            project_id=project_id,
            content_hash=validate_digest(desired_digest),
        )
        if media is None:
            return None
        self._verify_managed_text(media, current=current)
        return media

    # -- delayed prepared media -----------------------------------------

    def _prepared_media(
        self,
        frozen: FrozenTextBytes,
    ) -> tuple[PreparedMedia, Path]:
        """Create the one private 0600 temp used for an absent digest."""
        handle = tempfile.NamedTemporaryFile(
            mode="wb", prefix=".astrid-shot-text-", suffix=".txt", delete=False
        )
        temp_path = Path(handle.name)
        try:
            try:
                handle.write(frozen.value)
                handle.flush()
            finally:
                handle.close()
            mode = os.stat(temp_path).st_mode & 0o777
            if mode != 0o600:
                os.chmod(temp_path, 0o600)
            prepared = PreparedMedia(
                source_path=temp_path,
                digest=frozen.digest,
                byte_size=frozen.byte_size,
                media_kind="text",
                mime_type="text/plain",
                rel_path=f"{frozen.digest}.txt",
                probe={
                    "byte_size": frozen.byte_size,
                    "extension": ".txt",
                    "is_empty": frozen.byte_size == 0,
                },
            )
            return prepared, temp_path
        except BaseException:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise

    def materialize_absent_text(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        frozen: FrozenTextBytes,
        idempotency_key: str,
        actor_kind: str = "local",
    ) -> MediaReadModel:
        """Materialize one absent digest, cleaning its private temp always."""
        if self._media is None:
            raise ShotTextBindingValidationError("a Core MediaRepository is required")
        prepared, temp_path = self._prepared_media(frozen)
        try:
            materialized = self._media.materialize_prepared(
                uow,
                project_id=project_id,
                prepared=prepared,
                idempotency_key=idempotency_key,
                actor_kind=actor_kind,
                command_kind="core.media.import",
            )
            media = self._media.read_project_media(
                uow, project_id=project_id, media_id=materialized.media_id
            )
            if media is None:
                raise ShotTextBindingIntegrityError(detail="materialized_media_missing")
            return media
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    # -- mutation primitives --------------------------------------------

    def _write_set(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        frozen: FrozenTextBytes,
        expected_head: int,
        binding_id: str | None,
        shot_ref: str | None,
        kind: str | None,
        slot: str | None,
        idempotency_key: str,
        actor_kind: str,
    ) -> _MutationOutcome:
        project_id = _require_project(project_id)
        expected_head = _require_head(expected_head)
        idempotency_key = _require_key(idempotency_key)
        if self._media is None:
            raise ShotTextBindingValidationError("a Core MediaRepository is required")
        if expected_head == 0:
            if binding_id is not None or shot_ref is None or kind is None:
                raise ShotTextBindingValidationError("head 0 set requires a complete friendly selector")
            kind = validate_text_binding_kind(kind)
            slot = validate_text_binding_slot(slot, kind=kind)
            shot = self._resolve_shot(uow, project_id, shot_ref)
            binding_id = derive_text_binding_id(
                project_id=project_id, shot_id=str(shot["id"]), kind=kind, slot=slot
            )
            row = uow.query_one(
                "SELECT * FROM shot_text_bindings WHERE id = ?", (binding_id,)
            )
            if row is not None:
                if not (
                    str(row["project_id"]) == project_id
                    and str(row["shot_id"]) == str(shot["id"])
                    and str(row["kind"]) == kind
                    and row["slot"] == slot
                ):
                    raise ShotTextBindingConflictError(
                        reason="binding_id_collision", binding_id=binding_id
                    )
                stream = uow.query_one(
                    "SELECT head_seq FROM event_streams "
                    "WHERE id = ? AND project_id = ?",
                    (row["event_stream_id"], project_id),
                )
                actual = int(stream["head_seq"]) if stream is not None else 1
                raise ShotTextBindingStaleError(
                    expected_head=0, actual_head=actual, binding_id=binding_id
                )
            event_stream_id = derive_text_binding_stream_id(binding_id)
            if uow.query_one(
                "SELECT id FROM event_streams WHERE id = ?", (event_stream_id,)
            ) is not None:
                raise ShotTextBindingConflictError(reason="binding_id_collision", binding_id=binding_id)
            target = None
        else:
            target = self._resolve_binding(
                uow, project_id=project_id, binding_id=binding_id,
                shot_ref=shot_ref, kind=kind, slot=slot,
            )
            binding_id = str(target["id"])
            event_stream_id = str(target["event_stream_id"])
            stream = uow.query_one(
                "SELECT head_seq FROM event_streams "
                "WHERE id = ? AND project_id = ?",
                (event_stream_id, project_id),
            )
            actual = int(stream["head_seq"]) if stream is not None else -1
            if actual != expected_head:
                raise ShotTextBindingStaleError(expected_head=expected_head, actual_head=actual, binding_id=binding_id)
            current = self._media.read_project_media(
                uow, project_id=project_id, media_id=str(target["media_id"])
            )
            if current is None:
                raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=str(target["media_id"]))
            current_verified = self._verify_managed_text(current, current=True)
            self._verify_fingerprint(current_verified)
            if current.content_hash == frozen.digest:
                return _MutationOutcome(
                    mutation=ShotTextBindingMutation(
                        changed=False, binding=self._binding_row(uow, target)
                    ),
                    event_ids=(),
                    project_seqs=(),
                    txn_id="",
                )

        desired = self._resolve_desired_media(
            uow, project_id=project_id, desired_digest=frozen.digest
        )
        materialized_event = None
        if desired is None:
            media_key = f"{idempotency_key}:media:{frozen.digest}"
            desired = self.materialize_absent_text(
                uow, project_id=project_id, frozen=frozen,
                idempotency_key=media_key,
                actor_kind=actor_kind,
            )
            materialized_event = uow.query_one(
                "SELECT event_id, project_seq FROM events "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, media_key),
            )
            if materialized_event is None:
                raise ShotTextBindingIntegrityError(detail="materialized_event_missing")
        self._verify_fingerprint(self._verify_managed_text(desired, current=False))
        stamp = utc_now_iso()
        txn_id = uuid.uuid4().hex
        event_ids: list[str] = []
        project_seqs: list[int] = []
        if target is None:
            uow.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (event_stream_id, project_id, SHOT_TEXT_BINDING_STREAM_TYPE, binding_id, stamp),
            )
            data = {
                "binding_id": binding_id, "shot_id": str(shot["id"]),
                "kind": kind, "slot": slot, "media_id": desired.id,
                "content_hash": desired.content_hash,
            }
            changes = ["binding_id", "shot_id", "kind", "slot", "media_id"]
            event = self._events.append(
                uow, stream_id=event_stream_id, project_id=project_id,
                event_kind=SHOT_TEXT_BINDING_CREATED_EVENT_KIND, data=data,
                changes=changes, idempotency_key=idempotency_key,
                txn_id=txn_id, actor_kind=actor_kind,
                command_kind=SHOT_TEXT_BINDING_SET_COMMAND_KIND,
                expected_head_seq=0, created_at=stamp,
            )
            event_ids.append(event.event_id)
            project_seqs.append(event.project_seq)
            uow.execute(
                "INSERT INTO shot_text_bindings "
                "(id, project_id, shot_id, kind, slot, media_id, event_stream_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (binding_id, project_id, str(shot["id"]), kind, slot, desired.id, event_stream_id, stamp, stamp),
            )
        else:
            previous = self._media.read_project_media(
                uow, project_id=project_id, media_id=str(target["media_id"])
            )
            if previous is None:
                raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=str(target["media_id"]))
            event = self._events.append(
                uow, stream_id=event_stream_id, project_id=project_id,
                event_kind=SHOT_TEXT_BINDING_REBOUND_EVENT_KIND,
                data={
                    "binding_id": binding_id, "expected_head": expected_head,
                    "previous_media_id": previous.id,
                    "previous_content_hash": previous.content_hash,
                    "media_id": desired.id, "content_hash": desired.content_hash,
                    "updated_at": stamp,
                }, changes=["media_id", "updated_at"],
                idempotency_key=idempotency_key, txn_id=txn_id,
                actor_kind=actor_kind, command_kind=SHOT_TEXT_BINDING_SET_COMMAND_KIND,
                expected_head_seq=expected_head, created_at=stamp,
            )
            event_ids.append(event.event_id)
            project_seqs.append(event.project_seq)
            uow.execute(
                "UPDATE shot_text_bindings SET media_id = ?, updated_at = ? WHERE id = ? AND project_id = ?",
                (desired.id, stamp, binding_id, project_id),
            )
        result_row = uow.query_one("SELECT * FROM shot_text_bindings WHERE id = ?", (binding_id,))
        binding = self._binding_row(uow, result_row)
        if materialized_event is not None:
            event_ids.insert(0, str(materialized_event["event_id"]))
            project_seqs.insert(0, int(materialized_event["project_seq"]))
        mutation = ShotTextBindingMutation(changed=True, binding=binding)
        return _MutationOutcome(
            mutation=mutation,
            event_ids=tuple(event_ids),
            project_seqs=tuple(project_seqs),
            txn_id=txn_id,
        )

    def set(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        text: bytes,
        expected_head: int,
        idempotency_key: str,
        binding_id: str | None = None,
        shot_ref: str | None = None,
        kind: str | None = None,
        slot: str | None = None,
        actor_kind: str = "local",
    ) -> ShotTextBindingMutation:
        """Set complete text; caller bytes are frozen before UoW in normal use."""
        project_id = _require_project(project_id)
        expected_head = _require_head(expected_head)
        idempotency_key = _require_key(idempotency_key)
        frozen = freeze_text_bytes(text)
        request = {
            "project_id": project_id, "text_digest": frozen.digest,
            "text_size": frozen.byte_size, "expected_head": expected_head,
            "binding_id": binding_id, "shot_ref": shot_ref, "kind": kind, "slot": slot,
        }
        digest = request_hash(SHOT_TEXT_BINDING_SET_COMMAND_KIND, request)
        replay = self._receipts.check(
            uow, project_id=project_id, idempotency_key=idempotency_key,
            request_hash=digest, command_kind=SHOT_TEXT_BINDING_SET_COMMAND_KIND,
        )
        if replay is not None:
            return ShotTextBindingMutation.from_mapping(replay)
        result = self._write_set(
            uow, project_id=project_id, frozen=frozen, expected_head=expected_head,
            binding_id=binding_id, shot_ref=shot_ref, kind=kind, slot=slot,
            idempotency_key=idempotency_key, actor_kind=actor_kind,
        )
        if not result.mutation.changed:
            return result.mutation
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=digest,
            command_kind=SHOT_TEXT_BINDING_SET_COMMAND_KIND,
            txn_id=result.txn_id,
            first_project_seq=min(result.project_seqs),
            last_project_seq=max(result.project_seqs),
            event_ids=result.event_ids,
            result=result.mutation.to_dict(),
            primary_stream_id=result.mutation.binding.event_stream_id,
            resulting_stream_seq=result.mutation.binding.head,
        )
        return result.mutation

    def rebind(
        self,
        uow: UnitOfWork,
        *,
        project_id: str,
        media_id: str,
        expected_head: int,
        idempotency_key: str,
        binding_id: str | None = None,
        shot_ref: str | None = None,
        kind: str | None = None,
        slot: str | None = None,
        actor_kind: str = "local",
    ) -> ShotTextBindingMutation:
        """Rebind an existing binding to already-materialized text media."""
        project_id = _require_project(project_id)
        expected_head = _require_head(expected_head)
        if expected_head == 0:
            raise ShotTextBindingValidationError(
                "rebind requires a positive expected_head", detail="expected_head"
            )
        idempotency_key = _require_key(idempotency_key)
        request = {
            "project_id": project_id,
            "media_id": media_id,
            "expected_head": expected_head,
            "binding_id": binding_id,
            "shot_ref": shot_ref,
            "kind": kind,
            "slot": slot,
        }
        digest = request_hash(SHOT_TEXT_BINDING_REBIND_COMMAND_KIND, request)
        replay = self._receipts.check(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=digest,
            command_kind=SHOT_TEXT_BINDING_REBIND_COMMAND_KIND,
        )
        if replay is not None:
            return ShotTextBindingMutation.from_mapping(replay)
        target = self._resolve_binding(
            uow, project_id=project_id, binding_id=binding_id,
            shot_ref=shot_ref, kind=kind, slot=slot,
        )
        stream = uow.query_one(
            "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
            (target["event_stream_id"], project_id),
        )
        actual = int(stream["head_seq"]) if stream is not None else -1
        if actual != expected_head:
            raise ShotTextBindingStaleError(
                expected_head=expected_head, actual_head=actual, binding_id=str(target["id"])
            )
        if self._media is None:
            raise ShotTextBindingValidationError("a Core MediaRepository is required")
        current = self._media.read_project_media(
            uow, project_id=project_id, media_id=str(target["media_id"])
        )
        if current is None:
            raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=str(target["media_id"]))
        current_verified = self._verify_managed_text(current, current=True)
        self._verify_fingerprint(current_verified)
        desired = self._media.read_project_media(
            uow, project_id=project_id, media_id=media_id
        )
        if desired is None:
            raise ShotTextBindingNotFoundError(binding_id=media_id, project_id=project_id)
        desired_verified = self._verify_managed_text(desired, current=False)
        self._verify_fingerprint(desired_verified)
        if desired.id == current.id:
            return ShotTextBindingMutation(changed=False, binding=self._binding_row(uow, target))
        stamp = utc_now_iso()
        txn_id = uuid.uuid4().hex
        event = self._events.append(
            uow,
            stream_id=str(target["event_stream_id"]), project_id=project_id,
            event_kind=SHOT_TEXT_BINDING_REBOUND_EVENT_KIND,
            data={
                "binding_id": str(target["id"]), "expected_head": expected_head,
                "previous_media_id": current.id,
                "previous_content_hash": current.content_hash,
                "media_id": desired.id, "content_hash": desired.content_hash,
                "updated_at": stamp,
            },
            changes=["media_id", "updated_at"], idempotency_key=idempotency_key,
            txn_id=txn_id, actor_kind=actor_kind,
            command_kind=SHOT_TEXT_BINDING_REBIND_COMMAND_KIND,
            expected_head_seq=expected_head, created_at=stamp,
        )
        uow.execute(
            "UPDATE shot_text_bindings SET media_id = ?, updated_at = ? WHERE id = ? AND project_id = ?",
            (desired.id, stamp, target["id"], project_id),
        )
        updated = uow.query_one("SELECT * FROM shot_text_bindings WHERE id = ?", (target["id"],))
        mutation = ShotTextBindingMutation(
            changed=True, binding=self._binding_row(uow, updated)
        )
        self._receipts.record(
            uow,
            project_id=project_id,
            idempotency_key=idempotency_key,
            request_hash=digest,
            command_kind=SHOT_TEXT_BINDING_REBIND_COMMAND_KIND,
            txn_id=txn_id,
            first_project_seq=event.project_seq,
            last_project_seq=event.project_seq,
            event_ids=[event.event_id],
            result=mutation.to_dict(),
            primary_stream_id=mutation.binding.event_stream_id,
            resulting_stream_seq=mutation.binding.head,
        )
        return mutation


__all__ = [
    "FrozenTextBytes",
    "MAX_SHOT_TEXT_BYTES",
    "SHOT_TEXT_BINDING_APPLY_COMMAND_KIND",
    "SHOT_TEXT_BINDING_CREATED_EVENT_KIND",
    "SHOT_TEXT_BINDING_REBIND_COMMAND_KIND",
    "SHOT_TEXT_BINDING_REBOUND_EVENT_KIND",
    "SHOT_TEXT_BINDING_SET_COMMAND_KIND",
    "SHOT_TEXT_BINDING_STREAM_TYPE",
    "ShotTextBinding",
    "ShotTextBindingAmbiguousError",
    "ShotTextBindingConflictError",
    "ShotTextBindingError",
    "ShotTextBindingIntegrityError",
    "ShotTextBindingMediaCandidateError",
    "ShotTextBindingMutation",
    "ShotTextBindingNotFoundError",
    "ShotTextBindingRepository",
    "ShotTextBindingStaleError",
    "ShotTextBindingValidationError",
    "TEXT_BINDING_KINDS",
    "derive_text_binding_id",
    "derive_text_binding_stream_id",
    "freeze_text_bytes",
    "validate_text_binding_kind",
    "validate_text_binding_slot",
]
