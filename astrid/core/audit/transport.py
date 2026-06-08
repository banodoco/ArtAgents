from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

AUDIT_LEDGER_SCHEMA_VERSION = 2
HASH_ALGORITHM = "sha256"


class AuditLedgerError(RuntimeError):
    """Raised when the audit ledger cannot be safely appended or migrated."""


def canonical_json(payload: dict[str, Any]) -> str:
    """Return the canonical JSON representation used for audit hashes."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_record(payload: dict[str, Any]) -> str:
    """Hash an audit ledger record excluding the record's own hash field."""
    material = {key: value for key, value in payload.items() if key != "hash"}
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def finalize_record(payload: dict[str, Any], *, prev_hash: str | None) -> dict[str, Any]:
    """Return a schema_version:2 audit record with hash-chain metadata."""
    record = dict(payload)
    record["schema_version"] = AUDIT_LEDGER_SCHEMA_VERSION
    record["prev_hash"] = prev_hash
    record["hash_algorithm"] = HASH_ALGORITHM
    record.pop("hash", None)
    record["hash"] = hash_record(record)
    return record


def parse_ledger_bytes(data: bytes, *, require_final_newline: bool = False) -> list[dict[str, Any]]:
    """Parse audit JSONL bytes into records.

    ``load_ledger`` uses permissive parsing for v1 compatibility. Verification,
    append, and migration use ``require_final_newline=True`` so partial writes are
    detected before a new hash is chained onto a truncated tail.
    """
    if not data:
        return []
    if require_final_newline and not data.endswith(b"\n"):
        raise AuditLedgerError("ledger appears truncated: final line is not newline-terminated")

    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(data.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditLedgerError(f"line {line_number}: invalid JSON ({exc})") from exc
        if not isinstance(value, dict):
            raise AuditLedgerError(f"line {line_number}: ledger record is not a JSON object")
        records.append(value)
    return records


def verify_records(records: list[dict[str, Any]]) -> tuple[bool, int | None, str]:
    """Verify hash-chain fields on v2 records while accepting legacy v1 rows."""
    prev_hash: str | None = None
    saw_v2 = False
    for line_number, record in enumerate(records, start=1):
        schema_version = record.get("schema_version", 1)
        if schema_version != AUDIT_LEDGER_SCHEMA_VERSION:
            if saw_v2:
                return False, line_number, "legacy record after v2 hash-chain start"
            prev_hash = None
            continue

        saw_v2 = True
        if record.get("hash_algorithm") not in {None, HASH_ALGORITHM}:
            return False, line_number, f"unsupported hash_algorithm: {record.get('hash_algorithm')!r}"
        if record.get("prev_hash") != prev_hash:
            return False, line_number, "prev_hash does not match previous record hash"
        expected_hash = hash_record(record)
        if record.get("hash") != expected_hash:
            return False, line_number, "hash does not match canonical record payload"
        prev_hash = str(record["hash"])
    return True, None, "ok"


def verify_ledger_path(ledger_path: Path) -> tuple[bool, int | None, str]:
    if not ledger_path.is_file():
        return False, None, f"audit ledger not found: {ledger_path}"
    try:
        records = parse_ledger_bytes(ledger_path.read_bytes(), require_final_newline=True)
    except AuditLedgerError as exc:
        line_number = _line_number_from_error(str(exc))
        return False, line_number, str(exc)
    return verify_records(records)


def append_ledger_record(ledger_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Append one canonical v2 record under an exclusive file lock."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            data = handle.read()
            records = parse_ledger_bytes(data, require_final_newline=True)
            ok, line_number, reason = verify_records(records)
            if not ok:
                location = f"line {line_number}: " if line_number is not None else ""
                raise AuditLedgerError(f"cannot append to invalid audit ledger: {location}{reason}")
            prev_hash = _last_v2_hash(records)
            record = finalize_record(payload, prev_hash=prev_hash)
            handle.seek(0, os.SEEK_END)
            handle.write((canonical_json(record) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            return record
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def migrate_records_to_v2(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    migrated: list[dict[str, Any]] = []
    prev_hash: str | None = None
    for record in records:
        if record.get("schema_version") == AUDIT_LEDGER_SCHEMA_VERSION:
            next_record = dict(record)
            next_record["hash_algorithm"] = next_record.get("hash_algorithm") or HASH_ALGORITHM
            next_record["prev_hash"] = prev_hash
            next_record["hash"] = hash_record(next_record)
        else:
            next_record = finalize_record(record, prev_hash=prev_hash)
        migrated.append(next_record)
        prev_hash = str(next_record["hash"])
    return migrated


def serialize_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "".join(canonical_json(record) + "\n" for record in records)


def _last_v2_hash(records: list[dict[str, Any]]) -> str | None:
    for record in reversed(records):
        if record.get("schema_version") == AUDIT_LEDGER_SCHEMA_VERSION:
            value = record.get("hash")
            return str(value) if isinstance(value, str) else None
    return None


def _line_number_from_error(message: str) -> int | None:
    if not message.startswith("line "):
        return 1
    try:
        return int(message.split(":", 1)[0].split()[1])
    except (IndexError, ValueError):
        return 1
