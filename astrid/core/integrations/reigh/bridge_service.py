"""Repository-neutral bridge DTOs and errors (m1 plan step 18).

The repository-backed bridge (frozen ``docs/contracts/astrid-bridge-v10.md``)
is implemented as two layers:

- this module — **repository-neutral** frozen DTOs (health, project row,
  timeline row, timeline load, save request) and the typed bridge error
  family with the exact frozen status codes and error codes, plus the
  ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`` path derivation;
- ``astrid/packs/timeline/bridge.py`` — the pack adapter that maps
  repository reads/CAS saves and repository errors onto these DTOs/errors.

Nothing in this module imports a repository, an event service, or a pack:
the DTOs and errors are pure wire contracts, so any future repository
adapter (shots, references) reuses them unchanged. Internal receipt fields
(``txn_id``, ``request_hash``, ``idempotency_key``, project/stream
sequences, event ids) are deliberately absent from every DTO — receipt
secrecy (contract §7) is enforced by construction, not by filtering.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# Wire constants (frozen contract §2, §9)
# ---------------------------------------------------------------------------

ASTROID_DIR_NAME = ".astrid"
"""Managed-data directory under the projects root (decision artifact §5)."""

ASTROID_DATABASE_NAME = "astrid.sqlite3"
"""The repository-backed bridge database file (decision artifact §5)."""

BRIDGE_ERROR_ENVELOPE_KEYS: tuple[str, ...] = ("error", "detail")
"""Every error body is exactly ``{"error", "detail"}`` plus status extras."""

RECEIPT_SECRECY_FIELDS: frozenset[str] = frozenset(
    {
        "txn_id",
        "request_hash",
        "idempotency_key",
        "first_project_seq",
        "last_project_seq",
        "event_ids_json",
        "result_json",
        "event_ids",
        "project_seq",
        "stream_seq",
    }
)
"""Receipt/event internals that must never appear in any bridge response."""

# ---------------------------------------------------------------------------
# Path derivation
# ---------------------------------------------------------------------------


def derive_database_path(projects_root: str | Path) -> Path:
    """Return the repository-backed database path for a projects root.

    ``${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`` (decision artifact
    §5). The parent directory is *not* created here — the serve composition
    root creates it when the writer opens the database.
    """
    return Path(projects_root) / ASTROID_DIR_NAME / ASTROID_DATABASE_NAME


# ---------------------------------------------------------------------------
# Frozen DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """``GET /health`` payload (contract §3)."""

    ok: bool
    projects_root: str

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "projects_root": self.projects_root}


@dataclass(frozen=True, slots=True)
class ProjectRow:
    """One sorted ``GET /projects`` row (contract §4)."""

    slug: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name}


@dataclass(frozen=True, slots=True)
class TimelineRow:
    """One timeline discovery row (contract §5.1)."""

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
        }


@dataclass(frozen=True, slots=True)
class TimelineLoad:
    """The frozen load shape (contract §5.2) and save response (§6.2)."""

    timeline_id: str
    timeline_ulid: str
    slug: str
    name: str
    is_default: bool
    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    config_version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "timeline_ulid": self.timeline_ulid,
            "slug": self.slug,
            "name": self.name,
            "is_default": self.is_default,
            "config": dict(self.config),
            "registry": dict(self.registry),
            "config_version": self.config_version,
        }


@dataclass(frozen=True, slots=True)
class RunawayTransitionPage:
    """Versioned, snapshot-consistent page of typed Runaway rows."""

    project: str
    transitions: tuple[Mapping[str, Any], ...]
    timing_summary: Mapping[str, Any] | None
    snapshot: str
    total_count: int
    limit: int
    next_cursor: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": "v1",
            "project": self.project,
            # ``count`` remains the page count for compatibility with the
            # original viewer; total_count makes pagination explicit.
            "count": len(self.transitions),
            "total_count": self.total_count,
            "timing_summary": (
                dict(self.timing_summary)
                if self.timing_summary is not None
                else None
            ),
            "snapshot": self.snapshot,
            "page": {
                "limit": self.limit,
                "next_cursor": self.next_cursor,
            },
            "transitions": [dict(row) for row in self.transitions],
        }


_MISSING = object()


@dataclass(frozen=True, slots=True)
class TimelineSaveRequest:
    """The parsed ``POST .../save`` request body (contract §6.1).

    ``parse`` enforces the route-level validation before any repository
    call: ``config``/``registry`` must be JSON objects and
    ``expected_version`` must be an integer (a boolean is not a version).
    """

    config: Mapping[str, Any]
    registry: Mapping[str, Any]
    expected_version: int

    @classmethod
    def parse(cls, body: Any) -> TimelineSaveRequest:
        if not isinstance(body, Mapping):
            raise BridgeBodyError(
                "request body must be a JSON object"
            )
        config = body.get("config", _MISSING)
        registry = body.get("registry", _MISSING)
        expected_version = body.get("expected_version", _MISSING)
        if config is _MISSING or not isinstance(config, Mapping):
            raise BridgeConfigError("config must be a JSON object")
        if registry is _MISSING or not isinstance(registry, Mapping):
            raise BridgeRegistryError("registry must be a JSON object")
        if expected_version is _MISSING or isinstance(
            expected_version, bool
        ) or not isinstance(expected_version, int):
            raise BridgeExpectedVersionError(
                "expected_version must be an integer (a boolean is not a "
                "version)"
            )
        return cls(
            config=config,
            registry=registry,
            expected_version=expected_version,
        )


# ---------------------------------------------------------------------------
# Typed bridge errors (frozen contract §2.2)
# ---------------------------------------------------------------------------


class BridgeError(RuntimeError):
    """Base error for the repository-backed bridge.

    Every concrete error carries the frozen HTTP status and error code plus
    a human-readable detail; ``to_dict`` produces exactly the §2.2 envelope
    (``error``/``detail``) with the status-specific extras (``config_version``
    for 409, ``issues`` for 422). Internal receipt fields never appear.
    """

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "internal"

    def __init__(self, detail: str) -> None:
        self.detail: str = detail
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "detail": self.detail,
        }
        return payload


class BridgeBodyError(BridgeError):
    """``400 invalid_body`` — body is not valid JSON or not an object."""

    status_code = 400
    code = "invalid_body"


class BridgeConfigError(BridgeError):
    """``400 invalid_config`` — config missing or not an object."""

    status_code = 400
    code = "invalid_config"


class BridgeRegistryError(BridgeError):
    """``400 invalid_registry`` — registry missing or not an object."""

    status_code = 400
    code = "invalid_registry"


class BridgeExpectedVersionError(BridgeError):
    """``400 invalid_expected_version`` — not an integer (or a boolean)."""

    status_code = 400
    code = "invalid_expected_version"


class BridgeCursorError(BridgeError):
    """``400 invalid_cursor`` — malformed, stale, or cross-scope cursor."""

    status_code = 400
    code = "invalid_cursor"


class BridgeLimitError(BridgeError):
    """``400 invalid_limit`` — page size is absent from the supported range."""

    status_code = 400
    code = "invalid_limit"


class BridgeAuthenticationError(BridgeError):
    """``401 unauthorized`` — configured bearer token is missing/invalid."""

    status_code = 401
    code = "unauthorized"


class BridgeProtocolVersionError(BridgeError):
    """``426 protocol_version_mismatch`` — release client is incompatible."""

    status_code = 426
    code = "protocol_version_mismatch"


class BridgeRateLimitError(BridgeError):
    """``429 rate_limited`` — bounded local bridge admission is exhausted."""

    status_code = 429
    code = "rate_limited"


class BridgeForbiddenError(BridgeError):
    """``403 forbidden`` — Host or Origin violates the local bridge policy."""

    status_code = 403
    code = "forbidden"


class BridgePayloadTooLargeError(BridgeError):
    """``413 payload_too_large`` — request body exceeds the hard cap."""

    status_code = 413
    code = "payload_too_large"


class BridgeInvalidProjectError(BridgeError):
    """``400 invalid_project`` — the ``:slug`` fails project slug grammar."""

    status_code = 400
    code = "invalid_project"


class BridgeInvalidTimelineError(BridgeError):
    """``400 invalid_timeline`` — ``:ref`` is not UUID/ULID/slug."""

    status_code = 400
    code = "invalid_timeline"


class BridgeProjectNotFoundError(BridgeError):
    """``404 project_not_found`` — no project row for the slug."""

    status_code = 404
    code = "project_not_found"


class BridgeTimelineNotFoundError(BridgeError):
    """``404 timeline_not_found`` — no timeline for the ref in the project."""

    status_code = 404
    code = "timeline_not_found"


class BridgeVersionConflictError(BridgeError):
    """``409 timeline_version_conflict`` — stale expected head.

    Adds ``config_version`` (the current head) to the §2.2 envelope; the
    stale save changed zero rows.
    """

    status_code = 409
    code = "timeline_version_conflict"

    def __init__(self, detail: str, *, config_version: int) -> None:
        self.config_version: int = config_version
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["config_version"] = self.config_version
        return payload


@dataclass(frozen=True, slots=True)
class BridgeIssue:
    """One ``422 schema_incompatible`` issue (contract §2.2)."""

    pointer: str = ""
    code: str = "schema_incompatible"
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "pointer": self.pointer,
            "code": self.code,
            "message": self.message,
        }


class BridgeSchemaIncompatibleError(BridgeError):
    """``422 schema_incompatible`` — config/registry validation failed.

    Adds ``issues[]`` to the §2.2 envelope. A schema rejection is a typed
    422, never a connection-close 500 (contract §6.2).
    """

    status_code = 422
    code = "schema_incompatible"

    def __init__(
        self,
        detail: str,
        *,
        issues: list[BridgeIssue] | None = None,
    ) -> None:
        self.issues: list[BridgeIssue] = list(issues or [])
        if not self.issues:
            self.issues.append(BridgeIssue(message=detail))
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["issues"] = [issue.to_dict() for issue in self.issues]
        return payload


class BridgeInternalError(BridgeError):
    """``500 internal`` — an unexpected repository/service failure.

    Defensive only: the bridge surfaces typed 400/404/409/422 for every
    expected repository outcome. The body never includes exception details
    that could leak receipt or sequence internals.
    """

    status_code = 500
    code = "internal"


__all__ = [
    "ASTROID_DATABASE_NAME",
    "ASTROID_DIR_NAME",
    "BRIDGE_ERROR_ENVELOPE_KEYS",
    "BridgeAuthenticationError",
    "BridgeBodyError",
    "BridgeConfigError",
    "BridgeCursorError",
    "BridgeError",
    "BridgeExpectedVersionError",
    "BridgeForbiddenError",
    "BridgeInternalError",
    "BridgeInvalidProjectError",
    "BridgeInvalidTimelineError",
    "BridgeIssue",
    "BridgeLimitError",
    "BridgePayloadTooLargeError",
    "BridgeProtocolVersionError",
    "BridgeProjectNotFoundError",
    "BridgeRateLimitError",
    "BridgeRegistryError",
    "BridgeSchemaIncompatibleError",
    "BridgeTimelineNotFoundError",
    "BridgeVersionConflictError",
    "HealthStatus",
    "ProjectRow",
    "RECEIPT_SECRECY_FIELDS",
    "RunawayTransitionPage",
    "TimelineLoad",
    "TimelineRow",
    "TimelineSaveRequest",
    "derive_database_path",
]
