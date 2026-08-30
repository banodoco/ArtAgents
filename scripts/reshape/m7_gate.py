"""Fail-closed finalizer feasibility admission for the m7 milestone.

This module intentionally owns only the admission boundary.  The later m7
evidence gate may consume the record produced here, but this command never
runs the finalizer and never writes a plan ledger.  That makes the preflight
safe to run before execution, on resume, and again immediately before
publication.

The default paths describe the approved m7 plan.  All paths and the required
input set are injectable so the contract can be tested without touching the
working tree.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_NAME = "m7-dogfood-and-hardening-20260820-0835"
PLAN_HASH = "sha256:0792e68f5f92e6a7ab9a3b6052fa02518df7b8148b9a255162b161fbfea1ee49"
PLAN_VERSION = 2
GATE_SCHEMA = "astrid.m7_finalizer_admission.v1"
FINALIZER_COMMAND: tuple[str, ...] = ("make", "m7-gate")
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "m7"
DEFAULT_ADMISSION = DEFAULT_ARTIFACT_DIR / "finalizer-admission.json"
DEFAULT_PLAN = REPO_ROOT / ".megaplan" / "plans" / PLAN_NAME / "plan_v2.md"
DEFAULT_PLAN_META = DEFAULT_PLAN.with_name("plan_v2.meta.json")

# These are the source records the finalizer relies on.  They are deliberately
# explicit: silently dropping one makes a seemingly successful admission
# indeterminate.
DEFAULT_REQUIRED_INPUTS: tuple[Path, ...] = (
    DEFAULT_PLAN,
    DEFAULT_PLAN_META,
    DEFAULT_PLAN.with_name("plan_v1.meta.json"),
    DEFAULT_PLAN.with_name("state.json"),
    DEFAULT_PLAN.with_name("finalize.json"),
)

# Admission records are intentionally short-lived execution custody.  A
# record older than this cannot authorize a later plan mutation or finalizer.
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MIN_FREE_BYTES = 1 * 1024 * 1024
_CLOCK_SKEW_SECONDS = 30

ACCEPTANCE_SCHEMA = "astrid.m7_acceptance.v1"
DEFAULT_ACCEPTANCE = DEFAULT_ARTIFACT_DIR / "acceptance.json"
DEFAULT_DEFECTS = DEFAULT_ARTIFACT_DIR / "defects.md"

# Each item is backed by a whole-file selector.  The M7 dogfood journey is the
# integrated proof; the smaller selectors retain the failure-specific evidence
# that makes a green item diagnosable without claiming that one unrelated test
# substituted for it.  The selectors are intentionally explicit and never
# discovered from the filesystem.
GA_SELECTORS: dict[int, tuple[str, ...]] = {
    1: ("tests/v10/test_m7_fixture.py", "tests/v10/test_m7_hardening.py"),
    2: ("tests/v10/test_generation_roundtrip.py",),
    3: ("tests/v10/test_understanding_repository.py",),
    4: ("tests/v10/test_fanout.py",),
    5: ("tests/v10/test_task_races.py", "tests/v10/test_m7_hardening.py"),
    6: (
        "tests/v10/test_m7_bridge_contention.py",
    ),
    7: ("tests/v10/test_media_pipeline.py",),
    8: ("tests/v10/test_reference_conformance.py", "tests/v10/test_shot_conformance.py"),
    9: ("tests/v10/test_backup_restore.py", "tests/v10/test_m7_hardening.py"),
    10: ("tests/v10/test_m7_dogfood.py",),
}

GA_DESCRIPTIONS: dict[int, str] = {
    1: "fresh standard composition, catalog, and migration refusal",
    2: "credential-free generation and render traversal",
    3: "zero-task synchronous understanding and evidence",
    4: "fan-out, ordinals, dependencies, and group operations",
    5: "crash boundaries, terminal immutability, and stale-attempt exclusion",
    6: "repository-backed bridge journeys and contention",
    7: "media deduplication, mutation, and missing-location detection",
    8: "exact-media reference and shot round trips",
    9: "managed-media backup, restore, and doctor recovery",
    10: "clean credential-free release-candidate dogfood",
}

_ITEM11_SOURCE_PATHS = (
    "scripts/reshape/authority_lint.py",
    "astrid/core/gateway/dispatch.py",
    # The pre-cutover m6 gate was retired with the local application/serve
    # authority.  Keep item 11's provisional source evidence anchored to the
    # surviving doctor contract instead of making the gate depend on a deleted
    # test file.
    "tests/v10/test_doctor.py",
)
_ITEM12_SOURCE_PATHS = (
    "scripts/reshape/check_pack_factoring.py",
    "tests/v10/test_pack_factoring.py",
    "docs/architecture/software-engineering-pack-sketch.md",
)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _timestamp(value: dt.datetime | None = None) -> str:
    value = value or _utc_now()
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _status(ok: bool, detail: str = "") -> dict[str, object]:
    result: dict[str, object] = {"status": "pass" if ok else "fail"}
    if detail:
        result["detail"] = detail
    return result


def _as_command(command: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(command, str):
        command = tuple(shlex.split(command))
    else:
        command = tuple(str(part) for part in command)
    if not command or any(not part for part in command):
        raise ValueError("finalizer command must contain at least one non-empty token")
    return command


def validate_finalizer_command(
    command: str | Sequence[str] = FINALIZER_COMMAND,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[bool, str]:
    """Validate command shape and executable availability without executing it."""
    try:
        argv = _as_command(command)
    except ValueError as exc:
        return False, str(exc)
    executable = argv[0]
    if any(token in executable for token in (";", "&&", "||", "|", "\n")):
        return False, "finalizer command contains shell control syntax"
    resolved = shutil.which(executable, path=os.environ.get("PATH"))
    if resolved is None:
        candidate = (repo_root / executable).resolve()
        if not (candidate.is_file() and os.access(candidate, os.X_OK)):
            return False, f"finalizer executable is unavailable: {executable!r}"
    return True, "command is tokenized and executable is available"


def _check_repo_root(repo_root: Path) -> tuple[bool, str]:
    try:
        resolved = repo_root.expanduser().resolve()
    except OSError as exc:
        return False, f"repository root cannot be resolved: {exc}"
    if not resolved.is_dir():
        return False, f"repository root is not a directory: {resolved}"
    if not (resolved / ".git").exists() and resolved != REPO_ROOT.resolve():
        return False, f"repository root is not a checkout: {resolved}"
    return True, str(resolved)


def _input_record(path: Path, repo_root: Path) -> dict[str, object]:
    record: dict[str, object] = {"path": _relative_or_absolute(path, repo_root)}
    try:
        if not path.is_file():
            record.update({"present": False, "status": "fail", "reason": "missing"})
            return record
        record.update(
            {
                "present": True,
                "status": "pass",
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    except (OSError, ValueError) as exc:
        record.update({"present": True, "status": "indeterminate", "reason": str(exc)})
    return record


def _check_inputs(
    paths: Iterable[Path], *, repo_root: Path
) -> tuple[list[dict[str, object]], list[str]]:
    records = [_input_record(path, repo_root) for path in paths]
    errors = [
        f"required input unavailable: {record['path']} ({record.get('reason', 'missing')})"
        for record in records
        if record.get("status") != "pass"
    ]
    return records, errors


def _check_plan_identity(plan_path: Path, meta_path: Path) -> tuple[dict[str, object], list[str]]:
    check: dict[str, object] = {
        "version": PLAN_VERSION,
        "expected_hash": PLAN_HASH,
        "plan_path": str(plan_path),
        "meta_path": str(meta_path),
    }
    errors: list[str] = []
    if not plan_path.is_file() or not meta_path.is_file():
        check["status"] = "indeterminate"
        return check, ["plan identity inputs are unavailable"]
    try:
        actual_hash = _sha256_file(plan_path)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("plan metadata is not a JSON object")
        metadata_hash = metadata.get("hash")
        version = metadata.get("version")
        check.update({"actual_hash": actual_hash, "metadata_hash": metadata_hash, "metadata_version": version})
        if actual_hash != PLAN_HASH:
            errors.append(f"plan hash mismatch: expected {PLAN_HASH}, got {actual_hash}")
        if metadata_hash != PLAN_HASH:
            errors.append(f"plan metadata hash mismatch: expected {PLAN_HASH}, got {metadata_hash!r}")
        if version != PLAN_VERSION:
            errors.append(f"plan version mismatch: expected {PLAN_VERSION}, got {version!r}")
    except (OSError, ValueError, TypeError) as exc:
        check["status"] = "indeterminate"
        errors.append(f"plan identity is indeterminate: {exc}")
    check["status"] = "pass" if not errors else "fail"
    return check, errors


def _check_writable_directory(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        mode = path.stat().st_mode
        if not stat.S_ISDIR(mode):
            return False, f"artifact path is not a directory: {path}"
        if not os.access(path, os.W_OK | os.X_OK):
            return False, f"artifact directory is not writable: {path}"
        return True, str(path)
    except OSError as exc:
        return False, f"artifact directory is indeterminate: {exc}"


def _atomic_probe(path: Path) -> tuple[bool, dict[str, object]]:
    """Exercise replace in *path* and remove only files created by this probe."""
    token = next(tempfile._get_candidate_names())
    temporary = path / f".m7-atomic-probe-{token}.tmp"
    replacement = path / f".m7-atomic-probe-{token}.complete"
    details: dict[str, object] = {
        "temporary": str(temporary),
        "replacement": str(replacement),
        "removed": False,
    }
    try:
        temporary.write_bytes(b"m7 atomic replacement probe\n")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, replacement)
        if replacement.read_bytes() != b"m7 atomic replacement probe\n":
            raise OSError("atomic replacement content could not be verified")
        details["status"] = "pass"
        return True, details
    except (OSError, ValueError) as exc:
        details.update({"status": "indeterminate", "reason": str(exc)})
        return False, details
    finally:
        # Never glob or clean an entire artifact directory.  These are the
        # only two paths this invocation owns.
        removed = True
        for owned in (temporary, replacement):
            try:
                owned.unlink(missing_ok=True)
            except OSError:
                removed = False
        details["removed"] = removed and not temporary.exists() and not replacement.exists()


def _ledger_collisions(
    *,
    output_paths: Iterable[Path],
    immutable_paths: Iterable[Path],
    repo_root: Path,
) -> tuple[bool, dict[str, object], list[str]]:
    immutable = {path.expanduser().resolve() for path in immutable_paths}
    outputs = {path.expanduser().resolve() for path in output_paths}
    collisions = sorted(str(path) for path in outputs & immutable)
    # Also reject an output path located anywhere inside the immutable plan
    # ledger, including a path that does not exist yet.
    for output in outputs:
        for ledger in immutable:
            if output != ledger:
                try:
                    output.relative_to(ledger)
                except ValueError:
                    continue
                collisions.append(str(output))
                break
    collisions = sorted(set(collisions))
    details = {
        "immutable_paths": sorted(_relative_or_absolute(path, repo_root) for path in immutable),
        "output_paths": sorted(_relative_or_absolute(path, repo_root) for path in outputs),
        "collisions": collisions,
    }
    if collisions:
        return False, details, [f"immutable-ledger collision: {', '.join(collisions)}"]
    return True, details, []


def _record_payload(record: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if key not in {"content_hash", "record_hash"}}


def _content_hash(record: Mapping[str, object]) -> str:
    return _sha256_bytes(_canonical_json(_record_payload(record)))


def _write_atomic_json(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical_json(data))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_admission(
    *,
    repo_root: Path = REPO_ROOT,
    plan_path: Path = DEFAULT_PLAN,
    plan_meta_path: Path = DEFAULT_PLAN_META,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    admission_path: Path = DEFAULT_ADMISSION,
    required_inputs: Sequence[Path] | None = None,
    finalizer_command: str | Sequence[str] = FINALIZER_COMMAND,
    immutable_paths: Sequence[Path] | None = None,
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES,
    now: dt.datetime | None = None,
) -> dict[str, object]:
    """Run preflight checks and atomically retain the resulting admission.

    A failed preflight is still retained as a non-admitted record when it is
    safe to do so.  Callers must inspect ``admitted``; the record is never an
    authorization merely because it exists.
    """
    started = now or _utc_now()
    root = repo_root.expanduser().resolve()
    plan = plan_path.expanduser().resolve()
    meta = plan_meta_path.expanduser().resolve()
    artifacts = artifact_dir.expanduser().resolve()
    admission = admission_path.expanduser().resolve()
    try:
        command = _as_command(finalizer_command)
    except ValueError as exc:
        command = ()
        command_error = str(exc)
    else:
        command_error = ""

    checks: dict[str, object] = {}
    errors: list[str] = []

    ok, detail = _check_repo_root(root)
    checks["repository_root"] = _status(ok, detail)
    if not ok:
        errors.append(detail)

    command_ok, command_detail = (False, command_error) if command_error else validate_finalizer_command(command, repo_root=root)
    checks["finalizer_command"] = _status(command_ok, command_detail)
    if not command_ok:
        errors.append(command_detail)

    input_paths = tuple(path.expanduser().resolve() for path in (required_inputs or DEFAULT_REQUIRED_INPUTS))
    input_records, input_errors = _check_inputs(input_paths, repo_root=root)
    checks["required_inputs"] = {"status": "pass" if not input_errors else "fail", "records": input_records}
    errors.extend(input_errors)

    identity, identity_errors = _check_plan_identity(plan, meta)
    checks["plan_identity"] = identity
    errors.extend(identity_errors)

    writable, writable_detail = _check_writable_directory(artifacts)
    checks["artifact_directory"] = _status(writable, writable_detail)
    if not writable:
        errors.append(writable_detail)

    disk_ok = False
    disk_detail = "disk usage could not be determined"
    try:
        free = shutil.disk_usage(artifacts).free
        disk_ok = free >= min_free_bytes
        disk_detail = f"free_bytes={free}; required_bytes={min_free_bytes}"
    except OSError as exc:
        disk_detail = f"disk usage is indeterminate: {exc}"
    checks["disk_space"] = _status(disk_ok, disk_detail)
    if not disk_ok:
        errors.append(disk_detail)

    ledger = tuple(immutable_paths or ())
    if not ledger:
        ledger_root = plan.parent
        ledger = tuple(path for path in ledger_root.rglob("*") if path.is_file()) if ledger_root.is_dir() else ()
    output_paths = (admission, artifacts / "acceptance.json", artifacts / "defects.md")
    collision_ok, collision_details, collision_errors = _ledger_collisions(
        output_paths=output_paths, immutable_paths=ledger, repo_root=root
    )
    checks["immutable_ledger_collisions"] = _status(collision_ok, "no output path collides")
    checks["immutable_ledger_collisions"].update(collision_details)  # type: ignore[union-attr]
    errors.extend(collision_errors)

    probe_ok = False
    probe_details: dict[str, object] = {"status": "indeterminate", "removed": False}
    if writable and collision_ok:
        probe_ok, probe_details = _atomic_probe(artifacts)
        if not probe_ok:
            errors.append(str(probe_details.get("reason", "atomic probe failed")))
        if probe_details.get("removed") is not True:
            errors.append("atomic probe cleanup was indeterminate")
    else:
        probe_details["reason"] = "probe skipped because a prerequisite failed"
        errors.append("atomic probe is indeterminate because a prerequisite failed")
    checks["atomic_temporary_replacement"] = probe_details

    finished = _utc_now()
    record: dict[str, object] = {
        "schema": GATE_SCHEMA,
        "admitted": not errors,
        "timestamp": {"started_at": _timestamp(started), "finished_at": _timestamp(finished)},
        "created_at": _timestamp(finished),
        "tool": {
            "script": _relative_or_absolute(Path(__file__), root),
            "python": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "repo": {"root": str(root), "expected_root": str(REPO_ROOT.resolve())},
        "finalizer_command": list(command),
        "plan": {
            "version": PLAN_VERSION,
            "name": PLAN_NAME,
            "path": _relative_or_absolute(plan, root),
            "meta_path": _relative_or_absolute(meta, root),
            "expected_hash": PLAN_HASH,
            "actual_hash": identity.get("actual_hash"),
        },
        "inputs": input_records,
        "checks": checks,
        "errors": errors,
        "artifact_directory": _relative_or_absolute(artifacts, root),
        "admission_path": str(admission),
    }
    digest = _content_hash(record)
    record["content_hash"] = digest
    record["record_hash"] = digest
    if collision_ok:
        try:
            _write_atomic_json(admission, record)
        except OSError as exc:
            # Publication failure must revoke admission, even if the record
            # was otherwise green.  Do not retry or overwrite a ledger.
            record["admitted"] = False
            record["errors"] = [*errors, f"admission publication failed: {exc}"]
            record.pop("content_hash", None)
            record.pop("record_hash", None)
            digest = _content_hash(record)
            record["content_hash"] = digest
            record["record_hash"] = digest
    return record


def validate_admission(
    record: object,
    *,
    plan_path: Path = DEFAULT_PLAN,
    admission_path: Path | None = None,
    expected_plan_hash: str = PLAN_HASH,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: dt.datetime | None = None,
    expected_command: str | Sequence[str] = FINALIZER_COMMAND,
) -> list[str]:
    """Return all reasons *record* cannot authorize execution or resume."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["admission record is not a JSON object"]
    if record.get("schema") != GATE_SCHEMA:
        errors.append("admission schema mismatch")
    if record.get("admitted") is not True:
        errors.append("admission is not admitted")
    supplied_hashes = [record.get("content_hash"), record.get("record_hash")]
    present_hashes = [value for value in supplied_hashes if isinstance(value, str)]
    if len(present_hashes) != 2 or present_hashes[0] != present_hashes[1]:
        errors.append("admission content hashes conflict or are missing")
    elif present_hashes[0] != _content_hash(record):
        errors.append("admission content hash mismatch")
    plan = record.get("plan")
    if not isinstance(plan, dict):
        errors.append("admission plan identity is missing")
    else:
        if plan.get("expected_hash") != expected_plan_hash or plan.get("actual_hash") != expected_plan_hash:
            errors.append("admission plan hash mismatch")
        if plan.get("version") != PLAN_VERSION:
            errors.append("admission plan version mismatch")
    command = record.get("finalizer_command")
    try:
        expected = list(_as_command(expected_command))
    except ValueError:
        expected = []
    if command != expected:
        errors.append("admission finalizer command mismatch")
    timestamp = record.get("timestamp")
    finished_text = timestamp.get("finished_at") if isinstance(timestamp, dict) else record.get("created_at")
    try:
        finished = dt.datetime.fromisoformat(str(finished_text).replace("Z", "+00:00"))
        if finished.tzinfo is None:
            raise ValueError("timestamp has no timezone")
        age = (_utc_now() if now is None else now).astimezone(dt.timezone.utc) - finished.astimezone(dt.timezone.utc)
        if age.total_seconds() < -_CLOCK_SKEW_SECONDS:
            errors.append("admission timestamp is in the future")
        elif age.total_seconds() > max_age_seconds:
            errors.append("admission record is stale")
    except (TypeError, ValueError, OverflowError):
        errors.append("admission timestamp is missing or indeterminate")
    checks = record.get("checks")
    if not isinstance(checks, dict):
        errors.append("admission checks are missing")
    else:
        for name, check in checks.items():
            if not isinstance(check, dict) or check.get("status") != "pass":
                errors.append(f"admission check is not passing: {name}")
    if admission_path is not None and not admission_path.expanduser().resolve().is_file():
        errors.append("admission record is missing at its expected path")
    current_plan = plan_path.expanduser().resolve()
    if not current_plan.is_file():
        errors.append("current plan input is missing")
    else:
        try:
            if _sha256_file(current_plan) != expected_plan_hash:
                errors.append("current plan input is stale or mismatched")
        except OSError:
            errors.append("current plan input is indeterminate")
    return errors


def check_admission(
    path: Path = DEFAULT_ADMISSION,
    *,
    plan_path: Path = DEFAULT_PLAN,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: dt.datetime | None = None,
    expected_command: str | Sequence[str] = FINALIZER_COMMAND,
) -> tuple[dict[str, object], list[str]]:
    """Load and validate the retained record for execute/resume custody."""
    path = path.expanduser().resolve()
    if not path.is_file():
        return {}, [f"admission record is missing: {path}"]
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"admission record is indeterminate: {exc}"]
    return record, validate_admission(
        record,
        plan_path=plan_path,
        admission_path=path,
        max_age_seconds=max_age_seconds,
        now=now,
        expected_command=expected_command,
    )


# Explicit custody aliases make call sites read naturally at each boundary.
admit = run_admission
require_admission = check_admission


def _junit_counts(path: Path) -> dict[str, int]:
    """Return stable counts from a pytest JUnit document."""
    try:
        root = ET.parse(path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            raise ValueError("JUnit document has no testsuite")
        total = int(suite.get("tests", 0))
        failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        return {
            "total": total,
            "passed": max(0, total - failed - skipped),
            "failed": failed,
            "skipped": skipped,
        }
    except (ET.ParseError, OSError, TypeError, ValueError):
        return {"total": 0, "passed": 0, "failed": 1, "skipped": 0}


def _run_selector(
    item: int,
    selectors: Sequence[str],
    *,
    repo_root: Path,
    python: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, object]:
    """Run one whole-file GA selector and retain its log/count/hash evidence."""
    interpreter = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="m7-gate-") as temporary_dir:
        junit_path = Path(temporary_dir) / f"item-{item}.xml"
        argv = [
            "timeout",
            str(timeout_seconds),
            interpreter,
            "-m",
            "pytest",
            *selectors,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "--junit-xml",
            str(junit_path),
        ]
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            str(repo_root)
            if not existing_pythonpath
            else str(repo_root) + os.pathsep + existing_pythonpath
        )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                cwd=repo_root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds + 15,
            )
            returncode = completed.returncode
            log_text = completed.stdout + completed.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            returncode = 124
            log_text = f"m7 selector execution failed: {exc}\n"
        duration = time.monotonic() - started
        counts = _junit_counts(junit_path) if junit_path.is_file() else {
            "total": 0,
            "passed": 0,
            "failed": 1 if returncode else 0,
            "skipped": 0,
        }
        status = "pass" if returncode == 0 and counts["failed"] == 0 else "fail"
        return {
            "item": item,
            "selectors": list(selectors),
            "command": shlex.join(argv),
            "status": status,
            "stage": "executed-green" if status == "pass" else "executed-failed",
            "returncode": returncode,
            "duration_seconds": round(duration, 3),
            "counts": counts,
            "log": log_text,
            "log_sha256": _sha256_bytes(log_text.encode("utf-8")),
            "junit_sha256": (
                _sha256_file(junit_path) if junit_path.is_file() else None
            ),
        }


def _source_evidence(repo_root: Path, paths: Sequence[str], *, stage: str) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for relative in paths:
        path = repo_root / relative
        record: dict[str, object] = {"path": relative}
        try:
            if not path.is_file():
                record.update({"status": "missing"})
            else:
                record.update(
                    {
                        "status": "present",
                        "bytes": path.stat().st_size,
                        "sha256": _sha256_file(path),
                    }
                )
        except OSError as exc:
            record.update({"status": "indeterminate", "reason": str(exc)})
        records.append(record)
    return {"stage": stage, "files": records}


def _open_correctness_defects(path: Path) -> list[str]:
    """Find explicitly open severity-one/two correctness defects in Markdown."""
    if not path.is_file():
        return [f"defects ledger is missing: {path}"]
    findings: list[str] = []
    severity = re.compile(
        r"(?:severity\s*[- _:]*\s*(?:one|two|1|2)|\bS[12]\b)", re.IGNORECASE
    )
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        lowered = raw_line.lower()
        is_open = "- [ ]" in lowered or "open" in lowered
        is_correctness = "correctness" in lowered or "defect" in lowered or "bug" in lowered
        if is_open and is_correctness and severity.search(raw_line) and "no open" not in lowered:
            findings.append(raw_line.strip())
    return findings


def _performance_disposition(repo_root: Path) -> dict[str, object]:
    path = repo_root / "artifacts" / "m7" / "performance.json"
    if not path.is_file():
        return {
            "status": "unresolved",
            "reason": "performance evidence is absent; no approved budget was supplied",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "unresolved", "reason": f"performance evidence is indeterminate: {exc}"}
    budget_status = data.get("budget_status")
    return {
        "status": "unresolved" if budget_status in (None, "unresolved") else str(budget_status),
        "budget_status": budget_status,
        "path": "artifacts/m7/performance.json",
        "sha256": _sha256_file(path),
    }


def _defects_after_gate(path: Path, *, admission_hash: str, findings: Sequence[str]) -> str:
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# m7 defects ledger\n"
    if not existing.endswith("\n"):
        existing += "\n"
    disposition = [
        "",
        "## M7 gate disposition",
        "",
        f"- Finalizer admission record: `{admission_hash}`",
        f"- Open severity-one/two correctness defects: {'none' if not findings else 'see below' }.",
    ]
    if findings:
        disposition.extend(["", *[f"- {finding}" for finding in findings]])
    disposition.extend(
        [
            "- Item 6 external Reigh proof remains distinct and unresolved without an authorized pinned checkout.",
            "- Installed-artifact proof for items 11 and 12 remains pending m8.",
        ]
    )
    return existing + "\n".join(disposition) + "\n"


def _publish_pair(
    acceptance_path: Path,
    acceptance: Mapping[str, object],
    defects_path: Path,
    defects_text: str,
) -> None:
    """Publish both evidence documents via sibling temp files and rollback."""
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    defects_path.parent.mkdir(parents=True, exist_ok=True)
    old_acceptance = acceptance_path.read_bytes() if acceptance_path.is_file() else None
    old_defects = defects_path.read_bytes() if defects_path.is_file() else None
    temporary_paths: list[Path] = []
    try:
        for target, payload in (
            (acceptance_path, _canonical_json(acceptance)),
            (defects_path, defects_text.encode("utf-8")),
        ):
            fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            temporary = Path(name)
            temporary_paths.append(temporary)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary_paths[0], acceptance_path)
        os.replace(temporary_paths[1], defects_path)
    except OSError:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
        if old_acceptance is not None:
            _write_atomic_json(acceptance_path, json.loads(old_acceptance.decode("utf-8")))
        else:
            acceptance_path.unlink(missing_ok=True)
        if old_defects is not None:
            fd, name = tempfile.mkstemp(prefix=f".{defects_path.name}.", suffix=".tmp", dir=defects_path.parent)
            temporary = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(old_defects)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, defects_path)
        else:
            defects_path.unlink(missing_ok=True)
        raise


def run_gate(
    *,
    repo_root: Path = REPO_ROOT,
    admission_path: Path = DEFAULT_ADMISSION,
    acceptance_path: Path = DEFAULT_ACCEPTANCE,
    defects_path: Path = DEFAULT_DEFECTS,
    plan_path: Path = DEFAULT_PLAN,
    selectors: Mapping[int, Sequence[str]] | None = None,
    finalizer_command: str | Sequence[str] = FINALIZER_COMMAND,
    python: str | None = None,
    runner: Callable[[int, Sequence[str], Path], Mapping[str, object]] | None = None,
    resume: bool = False,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> tuple[dict[str, object], int]:
    """Run, record, and fail closed on the M7 GA evidence matrix."""
    root = repo_root.expanduser().resolve()
    admission, admission_errors = check_admission(
        admission_path,
        plan_path=plan_path,
        expected_command=finalizer_command,
        max_age_seconds=max_age_seconds,
    )
    if admission_errors:
        return (
            {
                "schema": ACCEPTANCE_SCHEMA,
                "status": "blocked",
                "stage": "admission",
                "admitted": False,
                "resume": resume,
                "admission": {"path": str(admission_path), "errors": admission_errors},
                "errors": admission_errors,
                "published": False,
            },
            1,
        )

    admission_hash = str(admission.get("content_hash"))
    selector_map = {
        item: tuple(paths) for item, paths in (selectors or GA_SELECTORS).items()
    }
    evidence: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for item in range(1, 11):
        item_selectors = selector_map.get(item)
        if not item_selectors:
            errors.append(f"GA item {item} has no admitted selector")
            continue
        missing = [path for path in item_selectors if not (root / path).is_file()]
        if missing:
            result: dict[str, object] = {
                "item": item,
                "selectors": list(item_selectors),
                "status": "fail",
                "stage": "selector-missing",
                "counts": {"total": 0, "passed": 0, "failed": 1, "skipped": 0},
                "error": f"missing selector file(s): {', '.join(missing)}",
            }
        elif runner is not None:
            result = dict(runner(item, item_selectors, root))
        else:
            result = _run_selector(item, item_selectors, repo_root=root, python=python)
        evidence[str(item)] = result
        if result.get("status") != "pass":
            errors.append(f"GA item {item} selector evidence is not green")

    defects = _open_correctness_defects(defects_path.expanduser().resolve())
    if defects:
        errors.append("open severity-one/two correctness defects are present")

    item11 = _source_evidence(root, _ITEM11_SOURCE_PATHS, stage="provisional-source-build")
    item11.update(
        {
            "status": "provisional",
            "label": "provisional",
            "reason": "source/build evidence only; installed artifact/help proof is deferred to m8",
        }
    )
    item12 = _source_evidence(root, _ITEM12_SOURCE_PATHS, stage="retained-m3-source-test")
    item12.update(
        {
            "status": "retained",
            "label": "retained",
            "reason": "retained m3 source/test evidence; installed-artifact rerun is pending m8",
        }
    )
    if any(record.get("status") != "present" for record in item11["files"]):
        errors.append("GA item 11 source/build evidence is incomplete")
    if any(record.get("status") != "present" for record in item12["files"]):
        errors.append("GA item 12 retained m3 source/test evidence is incomplete")

    unresolved = [
        {
            "id": "external-reigh-editor",
            "status": "unresolved",
            "reason": "authorized pinned external Reigh checkout was not supplied; in-tree bridge evidence is distinct",
        },
        {
            "id": "installed-artifact-items-11-12",
            "status": "deferred",
            "reason": "installed-artifact and package/help proof is an m8 gate",
        },
        {"id": "performance-budget", **_performance_disposition(root)},
    ]
    defects_text = _defects_after_gate(
        defects_path.expanduser().resolve(), admission_hash=admission_hash, findings=defects
    )
    acceptance: dict[str, object] = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "pass" if not errors else "fail",
        "ok": not errors,
        "stage": "m7-finalizer-evidence",
        "created_at": _timestamp(),
        "resume": resume,
        "finalizer_admission": {
            "status": "admitted",
            "hash": admission_hash,
            "path": _relative_or_absolute(admission_path.expanduser().resolve(), root),
        },
        "ga_items": {
            **{
                str(item): {
                    "description": GA_DESCRIPTIONS[item],
                    **evidence[str(item)],
                }
                for item in range(1, 11)
                if str(item) in evidence
            },
            "11": item11,
            "12": item12,
        },
        "commands": [
            evidence[str(item)].get("command")
            for item in range(1, 11)
            if evidence.get(str(item), {}).get("command")
        ],
        "unresolved_external_manual_gates": unresolved,
        "defects": {
            "path": _relative_or_absolute(defects_path.expanduser().resolve(), root),
            "open_severity_one_two_correctness": defects,
        },
        "errors": errors,
        "defects_sha256": _sha256_bytes(defects_text.encode("utf-8")),
    }
    acceptance["content_hash"] = _content_hash(acceptance)
    # Re-read the custody record after all selectors and immediately before
    # publication.  A plan or admission mutation must leave no partial gate
    # publication behind.
    latest_admission, final_admission_errors = check_admission(
        admission_path,
        plan_path=plan_path,
        expected_command=finalizer_command,
        max_age_seconds=max_age_seconds,
    )
    if final_admission_errors or latest_admission.get("content_hash") != admission_hash:
        final_errors = final_admission_errors or ["admission hash changed before publication"]
        acceptance["status"] = "blocked"
        acceptance["ok"] = False
        acceptance["errors"] = [*errors, *final_errors]
        acceptance["published"] = False
        return acceptance, 1
    try:
        _publish_pair(
            acceptance_path.expanduser().resolve(),
            acceptance,
            defects_path.expanduser().resolve(),
            defects_text,
        )
    except OSError as exc:
        acceptance["status"] = "blocked"
        acceptance["ok"] = False
        acceptance["errors"] = [*errors, f"evidence publication failed: {exc}"]
        acceptance["published"] = False
        return acceptance, 1
    acceptance["published"] = True
    return acceptance, 0 if not errors else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or validate m7 finalizer feasibility admission.")
    parser.add_argument("--check", action="store_true", help="validate an existing admission record")
    parser.add_argument("--resume", action="store_true", help="validate custody while running the gate in resume mode")
    parser.add_argument("--gate", action="store_true", help="run the admitted M7 GA evidence gate")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--plan-meta", type=Path, default=DEFAULT_PLAN_META)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--finalizer-command", default="make m7-gate")
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.gate:
        record, exit_code = run_gate(
            repo_root=args.repo_root,
            admission_path=args.admission,
            acceptance_path=args.artifact_dir / "acceptance.json",
            defects_path=args.artifact_dir / "defects.md",
            plan_path=args.plan,
            finalizer_command=args.finalizer_command,
            resume=args.resume,
            max_age_seconds=args.max_age_seconds,
        )
        print(json.dumps(record, sort_keys=True))
        return exit_code
    if args.check or args.resume:
        _record, errors = check_admission(
            args.admission,
            plan_path=args.plan,
            max_age_seconds=args.max_age_seconds,
            expected_command=args.finalizer_command,
        )
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"admitted={'true' if not errors else 'false'}")
        return 0 if not errors else 1
    record = run_admission(
        repo_root=args.repo_root,
        plan_path=args.plan,
        plan_meta_path=args.plan_meta,
        artifact_dir=args.artifact_dir,
        admission_path=args.admission,
        finalizer_command=args.finalizer_command,
    )
    print(f"admitted={'true' if record.get('admitted') else 'false'}")
    print(f"record_hash={record.get('record_hash', '')}")
    if record.get("admission_path"):
        print(f"admission={record['admission_path']}")
    for error in record.get("errors", []):
        print(f"ERROR: {error}", file=sys.stderr)
    return 0 if record.get("admitted") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
