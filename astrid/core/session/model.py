"""Session dataclass + explicit-root storage primitives.

A :class:`Session` is the per-tab binding record stored under
``~/.astrid/sessions/<ulid>.json``. Frozen — :func:`dataclasses.replace` is
used to produce updated copies (e.g. when WriterContext auto-rebinds the
``run_id`` after observing a fresh ``current_run.json``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal

from astrid.core.project.jsonio import ProjectJsonError, read_json, write_json_atomic
from astrid.core.util.time import utc_now_iso

SessionRole = Literal["writer", "reader", "orphan-pending"]
_ALLOWED_ROLES: tuple[SessionRole, ...] = ("writer", "reader", "orphan-pending")


class SessionValidationError(ValueError):
    """Raised when a session record fails validation."""


class SessionStoreError(RuntimeError):
    """Raised when explicit-root session storage cannot complete an operation."""


class SessionRecordNotFoundError(SessionStoreError, FileNotFoundError):
    """Raised when an explicit-root session record does not exist."""


class SessionRecordMalformedError(SessionStoreError):
    """Raised when an explicit-root session record cannot be decoded."""


def now_iso() -> str:
    return utc_now_iso()


@dataclass(frozen=True)
class Session:
    id: str
    project: str
    agent_id: str
    attached_at: str
    last_used_at: str
    # Snapshot/hint only — the on-disk session role records what the session
    # believed at write time. The writer lease is AUTHORITATIVE for the live
    # role; readers needing truth must consult the lease (see
    # lifecycle._derive_role_and_run_id and cli.cmd_status's lease correction).
    role: SessionRole
    timeline: str | None = None
    timeline_id: str | None = None
    run_id: str | None = None

    def with_changes(self, **changes: Any) -> "Session":
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        write_json_atomic(path, self.to_dict())

    @classmethod
    def from_dict(cls, raw: Any) -> "Session":
        if not isinstance(raw, dict):
            raise SessionValidationError("session record must be an object")
        try:
            role = raw["role"]
            if role not in _ALLOWED_ROLES:
                raise SessionValidationError(
                    f"session.role must be one of {_ALLOWED_ROLES}, got {role!r}"
                )
            return cls(
                id=_require_str(raw, "id"),
                project=_require_str(raw, "project"),
                timeline=_optional_str(raw, "timeline"),
                timeline_id=_optional_str(raw, "timeline_id"),
                run_id=_optional_str(raw, "run_id"),
                agent_id=_require_str(raw, "agent_id"),
                attached_at=_require_str(raw, "attached_at"),
                last_used_at=_require_str(raw, "last_used_at"),
                role=role,
            )
        except KeyError as exc:
            raise SessionValidationError(f"session missing field {exc.args[0]!r}") from exc

    @classmethod
    def from_json(cls, path: str | Path) -> "Session":
        return cls.from_dict(read_json(path))


class SessionStore:
    """Persist :class:`Session` records under an explicit ``session_root``.

    This SDK-facing storage helper never consults ``ASTRID_HOME``,
    ``Path.home()``, or any prompt-driven bootstrap path. Callers must pass the
    concrete directory that owns the session files.
    """

    def __init__(self, *, session_root: str | Path) -> None:
        self._session_root = Path(session_root).resolve()

    @property
    def session_root(self) -> Path:
        return self._session_root

    def session_path(self, session_id: str) -> Path:
        if not isinstance(session_id, str) or not session_id:
            raise SessionStoreError("session_id must be a non-empty string")
        return self._session_root / f"{session_id}.json"

    def save(self, session: Session) -> Path:
        path = self.session_path(session.id)
        session.to_json(path)
        return path

    def load(self, session_id: str) -> Session:
        path = self.session_path(session_id)
        try:
            return Session.from_json(path)
        except FileNotFoundError as exc:
            raise SessionRecordNotFoundError(
                f"session record not found: {path}"
            ) from exc
        except (ProjectJsonError, SessionValidationError) as exc:
            raise SessionRecordMalformedError(
                f"session record is malformed: {path}: {exc}"
            ) from exc

    def iter_sessions(self, *, skip_malformed: bool = False) -> list[Session]:
        if not self._session_root.exists():
            return []
        sessions: list[Session] = []
        for entry in sorted(self._session_root.iterdir()):
            if entry.suffix != ".json":
                continue
            try:
                sessions.append(self.load(entry.stem))
            except SessionStoreError:
                if skip_malformed:
                    continue
                raise
        return sessions

    def delete(self, session_id: str) -> Path:
        path = self.session_path(session_id)
        if not path.exists():
            raise SessionRecordNotFoundError(f"session record not found: {path}")
        path.unlink()
        return path


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise SessionValidationError(f"session.{key} must be a non-empty string")
    return value


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SessionValidationError(f"session.{key} must be null or a non-empty string")
    return value
