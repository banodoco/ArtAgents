"""Fail-closed validation, publication, and installed-lane collection for m8.

The gate is deliberately a small evidence boundary.  It does not rerun source
tests, infer a release matrix from the host, or turn retained m7 evidence into
packaged proof.  A caller supplies records produced by the installed-artifact
lanes and this module checks that every blocking record is complete, current,
and bound to the one wheel selected by :mod:`installed_artifact`.

The release publisher stages every output, validates the complete bundle, and
commits the six-file release set with rollback.  Failed lanes retain a compact
diagnostic under ``out/m8-gate`` without creating a partial ship declaration.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from scripts.reshape.installed_artifact import build_once
except ModuleNotFoundError:  # direct ``python scripts/reshape/m8_gate.py`` use
    from installed_artifact import build_once  # type: ignore[no-redef]


SCHEMA = "astrid.m8.evidence.v1"
ARTIFACT_IDENTITY_SCHEMA = "astrid.installed_artifact.v1"
JOURNEY_SCHEMA = "astrid.m8.installed_ga_journey.v1"
CONTRACT_SCHEMA = "astrid.m8.installed_contract.v1"
GATE_RESULT_SCHEMA = "astrid.m8.gate_result.v1"
ACCEPTANCE_SCHEMA = "astrid.m8.acceptance.v1"
AUTHORITY_CENSUS_SCHEMA = "astrid.m8.authority_census.v1"
PERFORMANCE_SCHEMA = "astrid.m8.performance.v1"
CLEAN_ACCOUNT_SCHEMA = "astrid.m8.clean_account_journey.v1"
HANDOFF_FILENAME = "handoff.md"
SHIP_FILENAME = "SHIP.md"
RELEASE_FILENAMES: tuple[str, ...] = (
    "acceptance.json",
    "authority-census.json",
    "performance.json",
    "clean-account-journey.json",
    HANDOFF_FILENAME,
    SHIP_FILENAME,
)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "m8"
DEFAULT_DIAGNOSTIC_DIR = REPO_ROOT / "out" / "m8-gate"

# These are the installed selectors represented by the preceding m8 lanes.
# ``source_selectors`` are context only and are never accepted as proof of a
# packaged lane.  Keeping both fields prevents a source test from being
# accidentally substituted while retaining the traceability of the GA map.
GA_ITEM_SELECTOR_MAP: dict[int, dict[str, Any]] = {
    1: {
        "description": "fresh standard composition, catalog, and migrations",
        "installed_selector": "installed-contract:catalog-migrations",
        "source_selectors": ("tests/v10/test_m8_installed_contract.py",),
        "evidence_class": "catalog_migrations",
    },
    2: {
        "description": "credential-free generation and render traversal",
        "installed_selector": "installed-journey:ga-item-2",
        "source_selectors": ("tests/v10/test_generation_roundtrip.py",),
        "evidence_class": "conformance",
    },
    3: {
        "description": "zero-task understanding and evidence",
        "installed_selector": "installed-journey:ga-item-3",
        "source_selectors": ("tests/v10/test_understanding_repository.py",),
        "evidence_class": "conformance",
    },
    4: {
        "description": "fan-out and dependency ordering",
        "installed_selector": "installed-journey:ga-item-4",
        "source_selectors": ("tests/v10/test_fanout.py",),
        "evidence_class": "conformance",
    },
    5: {
        "description": "task race and crash atomicity",
        "installed_selector": "installed-journey:ga-item-5",
        "source_selectors": (
            "tests/v10/test_task_races.py",
            "tests/v10/test_crash_atomicity.py",
        ),
        "evidence_class": "crash_contention",
    },
    6: {
        "description": "bridge CAS and contention",
        "installed_selector": "installed-journey:ga-item-6",
        "source_selectors": (
            "tests/integrations/reigh/test_local_bridge_server.py",
            "tests/v10/test_m7_bridge_contention.py",
        ),
        "evidence_class": "crash_contention",
    },
    7: {
        "description": "managed media import and verification",
        "installed_selector": "installed-journey:ga-item-7",
        "source_selectors": ("tests/v10/test_media_pipeline.py",),
        "evidence_class": "conformance",
    },
    8: {
        "description": "reference and shot round trips",
        "installed_selector": "installed-journey:ga-item-8",
        "source_selectors": (
            "tests/v10/test_reference_conformance.py",
            "tests/v10/test_shot_conformance.py",
        ),
        "evidence_class": "conformance",
    },
    9: {
        "description": "backup, restore, and doctor",
        "installed_selector": "installed-journey:ga-item-9",
        "source_selectors": ("tests/v10/test_backup_restore.py",),
        "evidence_class": "backup_restore",
    },
    10: {
        "description": "clean credential-free local-first journey",
        "installed_selector": "installed-journey:ga-item-10",
        "source_selectors": ("tests/v10/test_m7_dogfood.py",),
        "evidence_class": "clean_account",
    },
    11: {
        "description": "packaged artifact identity, matrix, and authority census",
        "installed_selector": "installed-artifact:identity-authority-matrix",
        "source_selectors": (
            "tests/v10/test_m8_packaging.py",
            "tests/v10/test_m8_installed_authority.py",
        ),
        "evidence_class": "authority_census",
    },
    12: {
        "description": "packaged reduced-composition factorability",
        "installed_selector": "installed-factoring:timeline-shots-references",
        "source_selectors": ("tests/v10/test_m8_installed_factoring.py",),
        "evidence_class": "catalog_migrations",
    },
}

# Public aliases used by release tooling and convenient for callers that prefer
# a selector-centric name.  The values are the same immutable contract.
GA_SELECTOR_MAP = GA_ITEM_SELECTOR_MAP
GA_ITEM_SELECTORS = GA_ITEM_SELECTOR_MAP

EVIDENCE_CLASSES: tuple[str, ...] = (
    "artifact_identity",
    "matrix_lanes",
    "authority_census",
    "catalog_migrations",
    "conformance",
    "crash_contention",
    "backup_restore",
    "performance",
    "clean_account",
    "manual",
)
BLOCKING_EVIDENCE_CLASSES = frozenset(EVIDENCE_CLASSES) - {"performance", "manual"}
DISALLOWED_LABELS = frozenset(
    {"source-only", "source_only", "provisional", "retained", "stale", "missing"}
)
PASS_STATUSES = frozenset({"pass", "passed", "green", "success", "ok"})
MANUAL_STATUSES = frozenset({"unresolved", "required", "pending"})


class M8GateError(ValueError):
    """Base error for malformed or unsafe m8 evidence."""


class EvidenceValidationError(M8GateError):
    """Raised by strict validation when one or more records fail closed."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(str(error) for error in errors)
        self.diagnostics_path: Path | None = None
        super().__init__("; ".join(self.errors) or "invalid m8 evidence")


class PublicationError(M8GateError):
    """Raised when the validated release set cannot be published atomically."""

    def __init__(self, message: str, *, diagnostics_path: Path | None = None):
        self.diagnostics_path = diagnostics_path
        super().__init__(message)


@dataclass(frozen=True)
class EvidenceValidation:
    """Stable result object for callers that prefer non-raising validation."""

    ok: bool
    errors: tuple[str, ...] = ()
    digest: str | None = None
    blocking_records: int = 0
    manual_records: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "ok": self.ok,
            "errors": list(self.errors),
            "wheel_sha256": self.digest,
            "blocking_records": self.blocking_records,
            "manual_records": self.manual_records,
        }


@dataclass(frozen=True)
class GateRun:
    """One build-once run and its retained installed lane records."""

    digest: str
    version: str
    artifact: Mapping[str, Any]
    lanes: tuple[Mapping[str, Any], ...]
    environment: Mapping[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "astrid.m8.installed_gate_run.v1",
            "artifact": dict(self.artifact),
            "wheel_sha256": self.digest,
            "installed_version": self.version,
            "lanes": [dict(lane) for lane in self.lanes],
            "environment": dict(self.environment),
        }


@dataclass(frozen=True)
class ReleasePublication:
    """Result of one successful, digest-bound m8 release publication."""

    artifact_dir: Path
    files: tuple[Path, ...]
    digest: str
    validation: EvidenceValidation
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": GATE_RESULT_SCHEMA,
            "status": "pass",
            "published": True,
            "artifact_dir": str(self.artifact_dir),
            "files": [str(path) for path in self.files],
            "wheel_sha256": self.digest,
            "created_at": self.created_at,
            "validation": self.validation.as_dict(),
        }


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value.lower()
    )


def _digest_values(record: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("wheel_sha256", "artifact_sha256", "digest"):
        value = record.get(key)
        if value is not None:
            if not _is_digest(value):
                raise M8GateError(f"{key} must be a lowercase SHA-256 digest")
            values.add(str(value).lower())
    return values


def _record_label(record: Mapping[str, Any], path: str) -> str:
    return str(record.get("lane") or record.get("selector") or path)


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _timestamp(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: object) -> object:
    """Return a JSON-safe copy without allowing publication to mutate input."""
    return json.loads(json.dumps(value, sort_keys=True))


def _infer_digest(evidence: Mapping[str, Any]) -> str:
    """Infer a digest only when artifact identity names exactly one digest."""
    artifact = evidence.get("artifact_identity")
    if artifact is None:
        raise M8GateError("selected wheel digest is required when artifact identity is missing")
    digests: set[str] = set()
    for path, record in _iter_records(artifact, "artifact_identity"):
        try:
            values = _digest_values(record)
        except M8GateError as exc:
            raise M8GateError(f"{path}: {exc}") from exc
        digests.update(values)
    if len(digests) != 1:
        raise M8GateError("selected wheel digest is ambiguous or missing")
    return next(iter(digests))


def _failure_summary(evidence: object) -> dict[str, object]:
    """Keep diagnostics useful while avoiding a second validation boundary."""
    if not isinstance(evidence, Mapping):
        return {"evidence_type": type(evidence).__name__}
    summary: dict[str, object] = {}
    for key in ("artifact_identity", *EVIDENCE_CLASSES, "lanes", "ga_items"):
        value = evidence.get(key)
        if value is None:
            continue
        if key in {"lanes", "ga_items"}:
            summary[key] = _json_safe(value)
            continue
        try:
            records = _iter_records(value, key)
        except M8GateError as exc:
            summary[key] = {"error": str(exc)}
            continue
        summary[key] = [
            {
                field: record.get(field)
                for field in ("lane", "selector", "status", "label", "error", "returncode")
                if field in record
            }
            for _path, record in records
        ]
    return summary


def _write_atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_diagnostic(
    diagnostics_dir: str | Path,
    *,
    stage: str,
    errors: Iterable[object],
    evidence: object = None,
    digest: str | None = None,
    now: datetime | None = None,
) -> Path | None:
    """Retain a failure record without letting diagnostics mask the failure."""
    directory = Path(diagnostics_dir).expanduser().resolve()
    payload: dict[str, object] = {
        "schema": "astrid.m8.gate_diagnostic.v1",
        "status": "blocked",
        "published": False,
        "stage": stage,
        "created_at": _timestamp(now),
        "errors": [str(error) for error in errors],
        "wheel_sha256": digest,
        "evidence": _failure_summary(evidence),
    }
    path = directory / "failure.json"
    try:
        _write_atomic_bytes(path, _canonical_json(payload))
    except (OSError, TypeError, ValueError):
        # A failed replace can be deliberately injected to test rollback.  A
        # direct final write is the last-resort diagnostic path and is safe
        # because this file is itself only a diagnostic, never a ship record.
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_canonical_json(payload))
        except (OSError, TypeError, ValueError):
            return None
    return path


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise M8GateError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise M8GateError(f"{field} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise M8GateError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iter_records(value: object, path: str) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        # A class envelope can contain a list under records/items/lanes, while
        # a single evidence record is itself a mapping.
        for key in ("records", "items", "lanes"):
            if key in value:
                child = value[key]
                if not isinstance(child, (list, tuple)):
                    raise M8GateError(f"{path}.{key} must be a list")
                result: list[tuple[str, Mapping[str, Any]]] = []
                for index, item in enumerate(child):
                    if not isinstance(item, Mapping):
                        raise M8GateError(f"{path}.{key}[{index}] must be an object")
                    result.append((f"{path}.{key}[{index}]", item))
                return result
        return [(path, value)]
    if isinstance(value, (list, tuple)):
        return [
            (f"{path}[{index}]", item)
            for index, item in enumerate(value)
            if isinstance(item, Mapping)
        ]
    raise M8GateError(f"{path} must be an object or list of objects")


def _status_error(record: Mapping[str, Any], path: str, *, manual: bool) -> str | None:
    labels = {
        str(record.get(key)).strip().lower()
        for key in ("status", "evidence_status", "stage", "label")
        if record.get(key) is not None
    }
    rejected = sorted(labels & DISALLOWED_LABELS)
    if rejected:
        return f"{path} has disallowed evidence status/label: {', '.join(rejected)}"
    status = str(record.get("status", "")).strip().lower()
    if manual:
        if status not in MANUAL_STATUSES:
            return f"{path} manual status must be unresolved/required/pending"
    elif status not in PASS_STATUSES:
        return f"{path} must have a passing status"
    return None


def _check_record(
    record: Mapping[str, Any],
    path: str,
    *,
    digest: str,
    now: datetime,
    max_age: timedelta,
    manual: bool = False,
) -> list[str]:
    errors: list[str] = []
    schema = record.get("schema")
    if not isinstance(schema, str) or not schema:
        errors.append(f"{path} schema is required")
    try:
        digests = _digest_values(record)
    except M8GateError as exc:
        errors.append(f"{path}: {exc}")
        digests = set()
    if not digests:
        errors.append(f"{path} is missing wheel/artifact digest")
    elif digests != {digest}:
        errors.append(f"{path} digest does not match the selected wheel")
    status_error = _status_error(record, path, manual=manual)
    if status_error:
        errors.append(status_error)
    started_value = record.get("started_at") or record.get("created_at")
    finished_value = record.get("finished_at") or record.get("updated_at")
    try:
        started = _parse_time(started_value, f"{path}.started_at/created_at")
        finished = _parse_time(finished_value or started_value, f"{path}.finished_at/updated_at")
        if finished < started:
            errors.append(f"{path} finishes before it starts")
        if now - finished > max_age:
            errors.append(f"{path} is stale")
        if finished - now > timedelta(minutes=5):
            errors.append(f"{path} is dated in the future")
    except M8GateError as exc:
        errors.append(str(exc))
    return errors


def _validate_performance(value: object, path: str, *, digest: str, now: datetime, max_age: timedelta) -> list[str]:
    errors: list[str] = []
    records = _iter_records(value, path)
    if not records:
        return [f"{path} has no timing records"]
    for record_path, record in records:
        errors.extend(_check_record(record, record_path, digest=digest, now=now, max_age=max_age))
        if record.get("report_only") is not True:
            errors.append(f"{record_path} performance evidence must be report-only")
        if record.get("budget_status") not in {"unresolved", "report-only"}:
            errors.append(f"{record_path} may not invent a blocking performance budget")
        if record.get("budget_source") not in {None, ""}:
            errors.append(f"{record_path} may not claim an unapproved budget source")
        if any(key in record for key in ("threshold_ms", "blocking_budget_ms", "budget_ms")):
            errors.append(f"{record_path} contains an invented blocking timing budget")
        timing = record.get("timing")
        if not isinstance(timing, Mapping):
            errors.append(f"{record_path}.timing must include environment details")
            continue
        if not isinstance(timing.get("samples_ms"), list) or not timing.get("samples_ms"):
            errors.append(f"{record_path}.timing.samples_ms is required")
        environment = record.get("environment")
        if not isinstance(environment, Mapping) or not all(
            isinstance(environment.get(key), str) and environment.get(key)
            for key in ("python", "platform", "system", "machine")
        ):
            errors.append(f"{record_path} timing record lacks environment details")
    return errors


def _validate_optional_lane_records(
    value: object,
    path: str,
    *,
    digest: str,
    now: datetime,
    max_age: timedelta,
) -> list[str]:
    """Reject retained failed installed lanes even when class records look green."""
    errors: list[str] = []
    try:
        records = _iter_records(value, path)
    except M8GateError as exc:
        return [str(exc)]
    if not records:
        return [f"{path} has no lane records"]
    for record_path, record in records:
        errors.extend(
            _check_record(record, record_path, digest=digest, now=now, max_age=max_age)
        )
        if str(record.get("status", "")).strip().lower() not in PASS_STATUSES:
            errors.append(
                f"{record_path} lane {_record_label(record, record_path)} is not passing"
            )
    return errors


def _validate_optional_ga_items(
    value: object,
    *,
    digest: str,
    now: datetime,
    max_age: timedelta,
) -> list[str]:
    """Validate an explicit 1–12 map when a caller supplies one."""
    errors: list[str] = []
    if isinstance(value, Mapping):
        records_by_item = {str(key): item for key, item in value.items()}
    elif isinstance(value, (list, tuple)):
        records_by_item = {str(index + 1): item for index, item in enumerate(value)}
    else:
        return ["ga_items must be an object or list"]
    for item in range(1, 13):
        path = f"ga_items[{item}]"
        record = records_by_item.get(str(item))
        if not isinstance(record, Mapping):
            errors.append(f"{path} is missing or not an object")
            continue
        errors.extend(_check_record(record, path, digest=digest, now=now, max_age=max_age))
    return errors


def validate_evidence(
    evidence: Mapping[str, Any],
    *,
    digest: str,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
    strict: bool = True,
) -> EvidenceValidation:
    """Validate a complete m8 evidence bundle against one wheel digest.

    The function is intentionally strict by default.  Every blocking class is
    required, every record must carry the selected digest and timestamps, and
    source/provisional/retained/stale evidence is never upgraded in place.
    ``manual`` is explicit unresolved evidence: it is accepted as a retained
    follow-up record but never counted as blocking automated proof.
    """
    errors: list[str] = []
    if not isinstance(evidence, Mapping):
        raise EvidenceValidationError(("evidence bundle must be an object",))
    if not _is_digest(digest):
        raise EvidenceValidationError(("selected wheel digest is not a lowercase SHA-256",))
    if evidence.get("schema") not in {SCHEMA, "astrid.m8.evidence_bundle.v1"}:
        errors.append("evidence bundle has an unsupported schema")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    max_age = timedelta(seconds=max_age_seconds)
    blocking_records = 0
    manual_records = 0

    artifact = evidence.get("artifact_identity")
    if artifact is None:
        errors.append("artifact_identity evidence is missing")
    else:
        for path, record in _iter_records(artifact, "artifact_identity"):
            blocking_records += 1
            errors.extend(_check_record(record, path, digest=digest, now=current, max_age=max_age))
            if record.get("schema") not in {ARTIFACT_IDENTITY_SCHEMA, "astrid.m8.artifact_identity.v1"}:
                errors.append(f"{path} has the wrong artifact identity schema")
            if not record.get("import_path") and not record.get("path"):
                errors.append(f"{path} lacks an installed artifact path")

    for class_name in EVIDENCE_CLASSES:
        if class_name in {"artifact_identity", "performance", "manual"}:
            continue
        value = evidence.get(class_name)
        if value is None:
            errors.append(f"{class_name} evidence is missing")
            continue
        records = _iter_records(value, class_name)
        if not records:
            errors.append(f"{class_name} evidence is empty")
        for path, record in records:
            blocking_records += 1
            errors.extend(_check_record(record, path, digest=digest, now=current, max_age=max_age))

    matrix = evidence.get("matrix_lanes")
    if matrix is not None:
        for path, record in _iter_records(matrix, "matrix_lanes"):
            for key in ("os", "python", "browser"):
                if not isinstance(record.get(key), str) or not record[key]:
                    errors.append(f"{path}.{key} is required")

    # Gate runners may retain the raw installed lane records alongside the
    # class summaries.  Those records are independently blocking: a failed
    # lane cannot be hidden by a passing summary assembled elsewhere.
    for lane_key in ("lanes", "lane_records"):
        if evidence.get(lane_key) is not None:
            errors.extend(
                _validate_optional_lane_records(
                    evidence[lane_key],
                    lane_key,
                    digest=digest,
                    now=current,
                    max_age=max_age,
                )
            )
    if evidence.get("ga_items") is not None:
        errors.extend(
            _validate_optional_ga_items(
                evidence["ga_items"], digest=digest, now=current, max_age=max_age
            )
        )

    if evidence.get("performance") is None:
        errors.append("performance evidence is missing")
    else:
        errors.extend(_validate_performance(evidence["performance"], "performance", digest=digest, now=current, max_age=max_age))

    manual = evidence.get("manual")
    if manual is None:
        errors.append("manual evidence must explicitly record unresolved physical-device ownership")
    else:
        manual_items = _iter_records(manual, "manual")
        if not manual_items:
            errors.append("manual evidence is empty")
        for path, record in manual_items:
            manual_records += 1
            errors.extend(_check_record(record, path, digest=digest, now=current, max_age=max_age, manual=True))
            if not record.get("owner"):
                errors.append(f"{path}.owner is required")
            if not record.get("device"):
                errors.append(f"{path}.device is required")
            if record.get("blocking") is not False:
                errors.append(f"{path} unresolved manual evidence must be non-blocking")

    result = EvidenceValidation(
        ok=not errors,
        errors=tuple(sorted(set(errors))),
        digest=digest,
        blocking_records=blocking_records,
        manual_records=manual_records,
    )
    if strict and not result.ok:
        raise EvidenceValidationError(result.errors)
    return result


def validate_m8_evidence(*args: Any, **kwargs: Any) -> EvidenceValidation:
    """Compatibility alias for :func:`validate_evidence`."""
    return validate_evidence(*args, **kwargs)


def evidence_is_valid(*args: Any, **kwargs: Any) -> bool:
    """Boolean convenience wrapper that never upgrades malformed evidence."""
    kwargs["strict"] = False
    return validate_evidence(*args, **kwargs).ok


def _release_paths(artifact_dir: Path) -> tuple[Path, ...]:
    return tuple(artifact_dir / filename for filename in RELEASE_FILENAMES)


def _snapshot_release_files(paths: Sequence[Path]) -> dict[Path, bytes | None]:
    snapshot: dict[Path, bytes | None] = {}
    for path in paths:
        if path.is_symlink():
            raise PublicationError(f"managed release path is a symlink: {path}")
        if path.exists() and not path.is_file():
            raise PublicationError(f"managed release path is not a file: {path}")
        snapshot[path] = path.read_bytes() if path.is_file() else None
    return snapshot


def _remove_release_files(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)


def _release_is_complete(snapshot: Mapping[Path, bytes | None]) -> bool:
    return bool(snapshot) and all(payload is not None for payload in snapshot.values())


def _restore_release_files(snapshot: Mapping[Path, bytes | None]) -> None:
    """Restore only the six files owned by this gate."""
    paths = tuple(snapshot)
    _remove_release_files(paths)
    if _release_is_complete(snapshot):
        for path, payload in snapshot.items():
            assert payload is not None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)


def _cleanup_incomplete_release_set(artifact_dir: Path) -> None:
    """Remove an old partial set while preserving an old complete release."""
    if not artifact_dir.is_dir() or artifact_dir.is_symlink():
        return
    paths = _release_paths(artifact_dir)
    try:
        snapshot = _snapshot_release_files(paths)
    except PublicationError:
        # A symlink or non-file at a managed name cannot be a valid release.
        _remove_release_files(paths)
        return
    if not _release_is_complete(snapshot):
        _remove_release_files(paths)
    try:
        if not any(artifact_dir.iterdir()):
            artifact_dir.rmdir()
    except OSError:
        pass


def _class_document(
    *,
    schema: str,
    value: object,
    digest: str,
    created_at: str,
) -> dict[str, object]:
    if isinstance(value, Mapping):
        document: dict[str, object] = dict(_json_safe(value))  # type: ignore[arg-type]
    else:
        document = {"records": _json_safe(value)}
    document.update(
        {
            "schema": schema,
            "status": "pass",
            "ok": True,
            "wheel_sha256": digest,
            "created_at": created_at,
            "evidence": _json_safe(value),
        }
    )
    return document


def _release_documents(
    evidence: Mapping[str, Any],
    *,
    digest: str,
    validation: EvidenceValidation,
    created_at: str,
) -> dict[str, bytes]:
    acceptance = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "pass",
        "ok": True,
        "created_at": created_at,
        "wheel_sha256": digest,
        "ga_selector_map": _json_safe(GA_ITEM_SELECTOR_MAP),
        "validation": validation.as_dict(),
        "evidence": _json_safe(evidence),
    }
    authority = _class_document(
        schema=AUTHORITY_CENSUS_SCHEMA,
        value=evidence["authority_census"],
        digest=digest,
        created_at=created_at,
    )
    performance = _class_document(
        schema=PERFORMANCE_SCHEMA,
        value=evidence["performance"],
        digest=digest,
        created_at=created_at,
    )
    clean_account = _class_document(
        schema=CLEAN_ACCOUNT_SCHEMA,
        value=evidence["clean_account"],
        digest=digest,
        created_at=created_at,
    )
    handoff = "\n".join(
        (
            "# Astrid m8 packaged GA handoff",
            "",
            "Status: ready for local release handoff",
            f"Wheel SHA-256: `{digest}`",
            "",
            "The six release documents were validated against one installed wheel and published as one gate result:",
            *[f"- `{filename}`" for filename in RELEASE_FILENAMES],
            "",
            "Performance evidence is report-only unless a separately approved budget exists.",
            "Unresolved physical-device evidence remains explicitly owned by the Release Owner.",
            "",
        )
    ).encode("utf-8")
    ship = "\n".join(
        (
            "# SHIP: Astrid m8 packaged GA",
            "",
            "Status: SHIP",
            f"Wheel SHA-256: `{digest}`",
            f"Acceptance: `{RELEASE_FILENAMES[0]}`",
            "",
            "This declaration exists only because every blocking evidence record passed the m8 gate.",
            "The artifact is a local, unsigned and unnotarized wheel as frozen by the release contract.",
            "",
        )
    ).encode("utf-8")
    return {
        "acceptance.json": _canonical_json(acceptance),
        "authority-census.json": _canonical_json(authority),
        "performance.json": _canonical_json(performance),
        "clean-account-journey.json": _canonical_json(clean_account),
        HANDOFF_FILENAME: handoff,
        SHIP_FILENAME: ship,
    }


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _commit_release_documents(
    artifact_dir: Path,
    documents: Mapping[str, bytes],
    snapshot: Mapping[Path, bytes | None],
) -> None:
    """Commit staged files in a rollback transaction owned by this function."""
    stage_dir = Path(tempfile.mkdtemp(prefix=".m8-release-", dir=artifact_dir.parent))
    paths = tuple(snapshot)
    try:
        for filename in RELEASE_FILENAMES:
            staged = stage_dir / filename
            staged.write_bytes(documents[filename])
            with staged.open("rb") as stream:
                os.fsync(stream.fileno())
        _fsync_directory(stage_dir)
        for path in paths:
            os.replace(stage_dir / path.name, path)
            _fsync_directory(artifact_dir)
        if not all(path.is_file() for path in paths):
            raise OSError("release publication completed with a missing managed file")
    except BaseException:
        try:
            _restore_release_files(snapshot)
        finally:
            raise
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
        _fsync_directory(artifact_dir.parent)


def publish_release_artifacts(
    evidence: Mapping[str, Any],
    *,
    digest: str | None = None,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    diagnostics_dir: str | Path = DEFAULT_DIAGNOSTIC_DIR,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
) -> ReleasePublication:
    """Validate and publish the complete m8 release set.

    Validation happens before creating ``artifacts/m8``.  Once validation is
    green, all six documents are written to a private sibling staging
    directory and renamed into place.  Any filesystem failure restores the
    prior complete set, or removes the managed files when the prior set was
    absent/partial.  Unrelated files in the artifact directory are preserved.
    """
    artifact_path = Path(artifact_dir).expanduser().resolve()
    diagnostic_path: Path | None = None
    selected_digest = digest.lower() if isinstance(digest, str) else None
    try:
        if not isinstance(evidence, Mapping):
            raise EvidenceValidationError(("evidence bundle must be an object",))
        if selected_digest is None:
            selected_digest = _infer_digest(evidence)
        validation = validate_evidence(
            evidence,
            digest=selected_digest,
            now=now,
            max_age_seconds=max_age_seconds,
            strict=False,
        )
        if not validation.ok:
            raise EvidenceValidationError(validation.errors)
        created_at = _timestamp(now)
        documents = _release_documents(
            evidence,
            digest=selected_digest,
            validation=validation,
            created_at=created_at,
        )
    except EvidenceValidationError as exc:
        _cleanup_incomplete_release_set(artifact_path)
        diagnostic_path = _write_diagnostic(
            diagnostics_dir,
            stage="validation",
            errors=exc.errors,
            evidence=evidence,
            digest=selected_digest,
            now=now,
        )
        exc.diagnostics_path = diagnostic_path
        raise
    except (M8GateError, OSError, TypeError, ValueError) as exc:
        _cleanup_incomplete_release_set(artifact_path)
        diagnostic_path = _write_diagnostic(
            diagnostics_dir,
            stage="preparation",
            errors=(str(exc),),
            evidence=evidence,
            digest=selected_digest,
            now=now,
        )
        raise PublicationError(str(exc), diagnostics_path=diagnostic_path) from exc

    try:
        if artifact_path.exists() and (artifact_path.is_symlink() or not artifact_path.is_dir()):
            raise OSError(f"artifact directory is not a directory: {artifact_path}")
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.mkdir(parents=True, exist_ok=True)
        paths = _release_paths(artifact_path)
        snapshot = _snapshot_release_files(paths)
        _commit_release_documents(artifact_path, documents, snapshot)
        _fsync_directory(artifact_path.parent)
        return ReleasePublication(
            artifact_dir=artifact_path,
            files=paths,
            digest=selected_digest,
            validation=validation,
            created_at=created_at,
        )
    except BaseException as exc:
        # _commit_release_documents restores the snapshot for commit errors;
        # this cleanup also covers directory setup and snapshot failures.
        _cleanup_incomplete_release_set(artifact_path)
        diagnostic_path = _write_diagnostic(
            diagnostics_dir,
            stage="publication",
            errors=(str(exc),),
            evidence=evidence,
            digest=selected_digest,
            now=now,
        )
        if isinstance(exc, PublicationError):
            exc.diagnostics_path = diagnostic_path
            raise
        raise PublicationError(str(exc), diagnostics_path=diagnostic_path) from exc


# Short aliases make the publication boundary discoverable to release scripts.
publish_artifacts = publish_release_artifacts
publish_release = publish_release_artifacts


def _default_lane_commands() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Small installed-only identity lanes used by the standalone collector."""
    return (
        ("installed-version", ("-c", "import importlib.metadata; print(importlib.metadata.version('astrid'))")),
        ("installed-import", ("-c", "import astrid; print(astrid.__file__)")),
    )


def collect_installed_lanes(
    repo_root: str | Path,
    *,
    workspace: str | Path | None = None,
    lane_commands: Sequence[tuple[str, Sequence[str]]] | None = None,
    install_dependencies: bool = False,
    lane_timeout: float = 120.0,
) -> GateRun:
    """Build one wheel and run all supplied commands through one harness.

    The harness owns source isolation, credential scrubbing, and identity
    records.  This function only composes lanes and checks that a failed lane
    cannot be mistaken for green evidence.
    """
    harness = build_once(
        repo_root,
        workspace=workspace,
        install_dependencies=install_dependencies,
    )
    try:
        commands = tuple(lane_commands or _default_lane_commands())
        records: list[Mapping[str, Any]] = []
        for lane, command in commands:
            record = harness.run_lane(lane, command, timeout=lane_timeout)
            records.append(record.as_dict())
        return GateRun(
            digest=harness.artifact_digest,
            version=harness.installed_version,
            artifact=harness.artifact.as_dict(),
            lanes=tuple(records),
            environment={
                "python": platform.python_version(),
                "platform": platform.platform(),
                "system": platform.system(),
                "machine": platform.machine(),
            },
        )
    finally:
        harness.close()


def _gate_evidence_from_run(run: GateRun, *, now: datetime | None = None) -> dict[str, object]:
    stamp = _timestamp(now)
    first_lane = run.lanes[0] if run.lanes else {}
    artifact_identity = {
        "schema": ARTIFACT_IDENTITY_SCHEMA,
        "status": "pass",
        "wheel_sha256": run.digest,
        "artifact_sha256": run.digest,
        "started_at": stamp,
        "finished_at": stamp,
        "path": run.artifact.get("path"),
        "import_path": first_lane.get("import_path"),
        "installed_version": run.version,
    }
    return {
        "schema": SCHEMA,
        "artifact_identity": artifact_identity,
        "lanes": list(run.lanes),
        "environment": dict(run.environment),
    }


def _blocked_gate_result(
    *,
    stage: str,
    errors: Iterable[object],
    diagnostic_path: Path | None,
    digest: str | None,
) -> dict[str, object]:
    return {
        "schema": GATE_RESULT_SCHEMA,
        "status": "blocked",
        "published": False,
        "stage": stage,
        "errors": [str(error) for error in errors],
        "diagnostic": str(diagnostic_path) if diagnostic_path else None,
        "wheel_sha256": digest,
    }


def run_gate(
    *,
    repo_root: str | Path = REPO_ROOT,
    evidence: Mapping[str, Any] | None = None,
    evidence_path: str | Path | None = None,
    digest: str | None = None,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    diagnostics_dir: str | Path = DEFAULT_DIAGNOSTIC_DIR,
    workspace: str | Path | None = None,
    install_dependencies: bool = False,
    max_age_seconds: int = 24 * 60 * 60,
    now: datetime | None = None,
) -> tuple[dict[str, object], int]:
    """Run the publication boundary and return a release result plus exit code.

    Supplying ``evidence_path`` is the handoff mode used by CI and release
    tooling.  With neither evidence argument, the function still builds one
    wheel through the shared harness and retains its installed identity lanes;
    publication then fails closed until the complete GA evidence bundle is
    supplied.
    """
    if evidence is not None and evidence_path is not None:
        error = "evidence and evidence_path are mutually exclusive"
        diagnostic = _write_diagnostic(
            diagnostics_dir, stage="input", errors=(error,), evidence=evidence, digest=digest, now=now
        )
        return _blocked_gate_result(
            stage="input", errors=(error,), diagnostic_path=diagnostic, digest=digest
        ), 1

    supplied: object = evidence
    if evidence_path is not None:
        path = Path(evidence_path).expanduser().resolve()
        try:
            supplied = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            diagnostic = _write_diagnostic(
                diagnostics_dir,
                stage="input",
                errors=(f"cannot load evidence: {exc}",),
                evidence={"path": str(path)},
                digest=digest,
                now=now,
            )
            return _blocked_gate_result(
                stage="input",
                errors=(f"cannot load evidence: {exc}",),
                diagnostic_path=diagnostic,
                digest=digest,
            ), 1
    elif supplied is None:
        try:
            installed = collect_installed_lanes(
                repo_root,
                workspace=workspace,
                install_dependencies=install_dependencies,
            )
            supplied = _gate_evidence_from_run(installed, now=now)
            digest = installed.digest
        except BaseException as exc:
            diagnostic = _write_diagnostic(
                diagnostics_dir,
                stage="installed-lanes",
                errors=(str(exc),),
                evidence=None,
                digest=digest,
                now=now,
            )
            return _blocked_gate_result(
                stage="installed-lanes", errors=(str(exc),), diagnostic_path=diagnostic, digest=digest
            ), 1

    try:
        publication = publish_release_artifacts(
            supplied,  # type: ignore[arg-type]
            digest=digest,
            artifact_dir=artifact_dir,
            diagnostics_dir=diagnostics_dir,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except EvidenceValidationError as exc:
        return _blocked_gate_result(
            stage="validation",
            errors=exc.errors,
            diagnostic_path=exc.diagnostics_path,
            digest=digest,
        ), 1
    except PublicationError as exc:
        return _blocked_gate_result(
            stage="publication",
            errors=(str(exc),),
            diagnostic_path=exc.diagnostics_path,
            digest=digest,
        ), 1
    return publication.as_dict(), 0


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", action="store_true", help="validate and publish the m8 release set")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--workspace")
    parser.add_argument("--evidence", type=Path, help="JSON evidence bundle to publish")
    parser.add_argument("--digest", help="selected wheel SHA-256; inferred from artifact identity when omitted")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DIAGNOSTIC_DIR)
    parser.add_argument("--max-age-seconds", type=int, default=24 * 60 * 60)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.gate:
        result, exit_code = run_gate(
            repo_root=args.repo_root,
            evidence_path=args.evidence,
            digest=args.digest,
            artifact_dir=args.artifact_dir,
            diagnostics_dir=args.out_dir,
            workspace=args.workspace,
            max_age_seconds=args.max_age_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return exit_code
    result = collect_installed_lanes(args.repo_root, workspace=args.workspace)
    text = json.dumps(result.as_dict(), indent=2, sort_keys=True)
    print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by release tooling
    raise SystemExit(_cli())


__all__ = [
    "ACCEPTANCE_SCHEMA",
    "ARTIFACT_IDENTITY_SCHEMA",
    "AUTHORITY_CENSUS_SCHEMA",
    "BLOCKING_EVIDENCE_CLASSES",
    "CLEAN_ACCOUNT_SCHEMA",
    "CONTRACT_SCHEMA",
    "DEFAULT_ARTIFACT_DIR",
    "DEFAULT_DIAGNOSTIC_DIR",
    "DISALLOWED_LABELS",
    "EVIDENCE_CLASSES",
    "EvidenceValidation",
    "EvidenceValidationError",
    "GA_ITEM_SELECTOR_MAP",
    "GA_ITEM_SELECTORS",
    "GA_SELECTOR_MAP",
    "GateRun",
    "JOURNEY_SCHEMA",
    "M8GateError",
    "PERFORMANCE_SCHEMA",
    "PublicationError",
    "RELEASE_FILENAMES",
    "ReleasePublication",
    "SCHEMA",
    "collect_installed_lanes",
    "evidence_is_valid",
    "publish_artifacts",
    "publish_release",
    "publish_release_artifacts",
    "run_gate",
    "validate_evidence",
    "validate_m8_evidence",
]
