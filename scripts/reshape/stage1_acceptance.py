"""Build the hash-linked Astrid Stage 1 acceptance bundle.

The Stage 1 gate is an evidence *aggregator*, not an evidence generator.  It
only consumes receipts that were produced by the launch, conformance,
migration, and security lanes.  Every accepted check must point at at least
one retained, hashed artifact.  Consequently a report can be ``blocked`` or
``fail`` but can never become ``pass`` from prose, an old M7 report, or an
empty directory.

The input directory is a portable evidence bundle.  Each JSON receipt has the
shape declared in ``docs/contracts/stage1-acceptance-evidence-v1.schema.json``.
The command writes two deterministic outputs (``acceptance.json`` and
``ASTRID-BETA.md``) atomically.  Timestamps are derived from receipt
timestamps, so regenerating a bundle produces the same hashes.

Usage::

    python3 -m scripts.reshape.stage1_acceptance \
        --evidence-dir .astrid-convergence/stage1-evidence \
        --output-dir .astrid-convergence/stage1-acceptance

Exit status is 0 only when every required receipt/check is present and
verified.  A missing or malformed receipt writes a blocked bundle and exits 1.
No live migration, network, or render receipt is created by this module.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_SCHEMA = "astrid.stage1.evidence.receipt.v1"
ACCEPTANCE_SCHEMA = "astrid.stage1.acceptance.v1"
REDACTION_VERSION = "astrid.evidence.redaction.v1"
HASH_PREFIX = "sha256:"

REQUIRED_CATEGORIES: tuple[str, ...] = (
    "source_identity",
    "dependency_locks",
    "source_manifests",
    "schema_contracts",
    "authority_census",
    "capability_census",
    "cold_launch",
    "lifecycle",
    "ready_capabilities",
    "render",
    "second_client",
    "conformance",
    "minimum_correctness",
    "migration",
    "backup_restore",
    "rollback",
    "doctor",
    "security",
    "network",
    "filesystem",
    "static_scans",
    "docs",
    "isolated_composition",
)

# These identifiers are the blocking rows from §§10.1–10.3, §11, and §13 of
# reigh-app/docs/local-runtime/01-astrid-beta.md.  They are intentionally
# explicit rather than discovered from filenames or receipt prose.
CHECK_CATEGORY: dict[str, str] = {
    # §10.1 — launch, persistence, migration
    "10.1.clean-editable-setup": "cold_launch",
    "10.1.legacy-root-refusal": "cold_launch",
    "10.1.single-realm-reuse": "cold_launch",
    "10.1.incompatible-runtime-fail-closed": "cold_launch",
    "10.1.concurrent-launch-one-owner": "cold_launch",
    "10.1.restart-reboot-fencing": "cold_launch",
    "10.1.discovery-credential-paths": "cold_launch",
    "10.1.migration-backup-activation-rollback": "migration",
    "10.1.doctor-integrity-recovery": "doctor",
    # §10.2 — product and second-client capability contract
    "10.2.project-document-crud": "lifecycle",
    "10.2.timeline-shot-reference-lifecycle": "lifecycle",
    "10.2.managed-media-cas": "lifecycle",
    "10.2.task-run-observation": "lifecycle",
    "10.2.required-capability-render-provenance": "ready_capabilities",
    "10.2.experiment-review-evidence": "lifecycle",
    "10.2.restart-persistence": "lifecycle",
    "10.2.generic-host-render-closure": "render",
    "10.2.recorded-agent-journey": "isolated_composition",
    "10.2.second-client": "second_client",
    "10.2.settlement-reservation-low-space": "conformance",
    "10.2.ready-capability-registration": "capability_census",
    # §10.3 — correctness and authority proof
    "10.3.negative-idempotency-version-digest-lease-settlement": "minimum_correctness",
    "10.3.termination-restart-fence": "minimum_correctness",
    "10.3.backup-restore-verify": "backup_restore",
    "10.3.security-credential-actors-loopback": "security",
    "10.3.static-import-dependency-bans": "static_scans",
    "10.3.network-no-hosted": "network",
    "10.3.realm-root": "filesystem",
    "10.3.cas-append-only-no-gc": "filesystem",
    "10.3.process-boundaries": "isolated_composition",
    "10.3.docs-no-retired-authority": "docs",
    "10.3.zero-unclassified": "authority_census",
    # §11 — definition of done
    "11.01.configure-and-launch": "cold_launch",
    "11.02.one-compatible-realm": "cold_launch",
    "11.03.project-facts-in-sqlite": "lifecycle",
    "11.04.media-managed-cas": "lifecycle",
    "11.05.timeline-shot-reference": "lifecycle",
    "11.06.task-protocol-recovery": "lifecycle",
    "11.07.every-advertised-ready-capability": "ready_capabilities",
    "11.08.outputs-events-receipts-after-restart": "lifecycle",
    "11.09.working-notes-no-authority": "docs",
    "11.10.backup-restore-export-tombstone-purge": "backup_restore",
    "11.11.no-legacy-paths-or-hidden-dependency": "static_scans",
    "11.12.editable-journey-and-second-client": "second_client",
    "11.13.rollback-archive-recovery": "rollback",
    # §13 — evidence and handoff checklist
    "13.01.reviewed-ddl-openapi-json-schemas": "schema_contracts",
    "13.02.reproducible-environments-and-revisions": "source_identity",
    "13.02.dependency-locks": "dependency_locks",
    "13.03.hash-recorded-beta-manifest": "source_manifests",
    "13.04.authority-and-capability-censuses": "authority_census",
    "13.05.migration-backup-activation-rollback": "migration",
    "13.06.machine-readable-acceptance-report": "conformance",
    "13.07.typescript-second-client-core": "second_client",
    "13.08.deletion-proof": "static_scans",
    "13.09.diagnostic-bundle": "doctor",
    "13.10.beta-document-and-deferred-risks": "docs",
}

REQUIRED_CHECKS: tuple[str, ...] = tuple(CHECK_CATEGORY)
LIVE_CATEGORIES = frozenset(
    {
        "cold_launch",
        "render",
        "second_client",
        "migration",
        "backup_restore",
        "rollback",
        "doctor",
        "security",
        "network",
        "filesystem",
    }
)
_HEX64 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_SECRET_KEY = re.compile(
    r"(?:secret|token|password|passwd|api[_-]?key|authorization|cookie|private[_-]?key)",
    re.IGNORECASE,
)
_ABS_USER_PATH = re.compile(r"/(?:Users|home)/[^/\s]+")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_ASSIGNMENT = re.compile(
    r"(?i)\b(?:token|password|secret|api[_-]?key)\s*=\s*[^\s,;]+"
)


class AcceptanceError(ValueError):
    """Raised only for programmer-facing API misuse; input errors are recorded."""


def canonical_json(value: object) -> bytes:
    """Return the canonical bytes used for every evidence hash."""

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return HASH_PREFIX + digest.hexdigest()


def _iso_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _redact(value: object, *, key: str = "") -> object:
    """Redact credential-shaped values and machine-user paths recursively."""

    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, key=key) for item in value]
    if isinstance(value, str):
        redacted = _BEARER.sub("Bearer [REDACTED]", value)
        redacted = _ASSIGNMENT.sub(lambda match: match.group(0).split("=", 1)[0] + "=[REDACTED]", redacted)
        return _ABS_USER_PATH.sub(lambda match: match.group(0).rsplit("/", 1)[0] + "/<user>", redacted)
    return value


def _safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return "<external-artifact>"


def _artifact_path(raw_path: object, *, receipt_path: Path, evidence_dir: Path) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = evidence_dir / candidate
        if not candidate.exists():
            candidate = receipt_path.parent / raw_path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(evidence_dir.resolve())
    except (OSError, ValueError):
        # Retained artifacts must be in the portable evidence bundle.  An
        # external absolute path is not reproducible and is rejected.
        return None
    return resolved


def _validate_artifact(
    raw: object,
    *,
    receipt_path: Path,
    evidence_dir: Path,
    errors: list[str],
) -> dict[str, object] | None:
    if not isinstance(raw, Mapping):
        errors.append(f"{receipt_path.name}: artifact is not an object")
        return None
    raw_path = raw.get("path")
    path = _artifact_path(raw_path, receipt_path=receipt_path, evidence_dir=evidence_dir)
    expected = raw.get("sha256")
    if path is None:
        errors.append(f"{receipt_path.name}: artifact path is not retained in evidence bundle")
        return None
    if not path.is_file():
        errors.append(f"{receipt_path.name}: artifact is missing: {_safe_relpath(path, evidence_dir)}")
        return None
    if not _valid_hash(expected):
        errors.append(f"{receipt_path.name}: artifact has invalid sha256")
        return None
    try:
        actual = sha256_file(path)
    except OSError as exc:
        errors.append(f"{receipt_path.name}: artifact cannot be read ({exc})")
        return None
    expected_digest = str(expected)
    if not expected_digest.startswith(HASH_PREFIX):
        expected_digest = HASH_PREFIX + expected_digest
    if actual != expected_digest:
        errors.append(
            f"{receipt_path.name}: artifact hash mismatch for {_safe_relpath(path, evidence_dir)}"
        )
        return None
    return {
        "path": _safe_relpath(path, evidence_dir),
        "sha256": actual,
        "kind": str(raw.get("kind", "evidence")),
    }


def _validate_receipt(
    path: Path,
    *,
    evidence_dir: Path,
) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
    errors: list[str] = []
    checks: list[dict[str, object]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [], [f"{_safe_relpath(path, evidence_dir)}: cannot read JSON receipt ({exc})"]
    if not isinstance(data, Mapping):
        return None, [], [f"{path.name}: receipt is not an object"]
    if data.get("schema") != RECEIPT_SCHEMA:
        return None, [], [f"{path.name}: unsupported receipt schema"]
    receipt_id = data.get("receipt_id")
    category = data.get("category")
    status = data.get("status")
    observed_at = _iso_timestamp(data.get("observed_at"))
    command = data.get("command")
    observations = data.get("observations")
    raw_checks = data.get("checks")
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        errors.append(f"{path.name}: receipt_id is required")
    if category not in REQUIRED_CATEGORIES:
        errors.append(f"{path.name}: unknown or missing category")
    if status not in {"pass", "fail", "blocked"}:
        errors.append(f"{path.name}: status must be pass, fail, or blocked")
    if observed_at is None:
        errors.append(f"{path.name}: observed_at must be timezone-aware ISO-8601")
    if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
        errors.append(f"{path.name}: command must be a non-empty argv list")
    if not isinstance(observations, Mapping) or not observations:
        errors.append(f"{path.name}: observations must be a non-empty object")
    if category in LIVE_CATEGORIES and isinstance(observations, Mapping):
        mode = observations.get("evidence_mode")
        if mode in {"synthetic", "narrative", "manual_claim", "fixture"}:
            errors.append(f"{path.name}: live category cannot use synthetic/narrative evidence")
    if not isinstance(raw_checks, list) or not raw_checks:
        errors.append(f"{path.name}: checks must be a non-empty list")
        raw_checks = []
    for raw_check in raw_checks:
        if not isinstance(raw_check, Mapping):
            errors.append(f"{path.name}: check is not an object")
            continue
        check_id = raw_check.get("id")
        check_status = raw_check.get("status")
        check_observations = raw_check.get("observations")
        raw_artifacts = raw_check.get("artifacts")
        if check_id not in CHECK_CATEGORY:
            errors.append(f"{path.name}: unknown check id: {check_id!r}")
            continue
        if category != CHECK_CATEGORY[check_id]:
            errors.append(
                f"{path.name}: check {check_id} belongs to {CHECK_CATEGORY[check_id]}, not {category}"
            )
        if check_status not in {"pass", "fail", "blocked"}:
            errors.append(f"{path.name}: check {check_id} has invalid status")
        if not isinstance(check_observations, Mapping) or not check_observations:
            errors.append(f"{path.name}: check {check_id} needs machine observations")
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            errors.append(f"{path.name}: check {check_id} needs retained artifacts")
            raw_artifacts = []
        artifacts = []
        for item in raw_artifacts:
            artifact = _validate_artifact(
                item,
                receipt_path=path,
                evidence_dir=evidence_dir,
                errors=errors,
            )
            if artifact is not None:
                artifacts.append(artifact)
        if not artifacts:
            errors.append(f"{path.name}: check {check_id} has no verified artifacts")
        checks.append(
            {
                "id": str(check_id),
                "status": str(check_status),
                "observations": _redact(check_observations),
                "artifacts": artifacts,
            }
        )
    if status == "pass" and any(item.get("status") != "pass" for item in checks):
        errors.append(f"{path.name}: passing receipt contains a non-passing check")
    normalized = {
        "receipt_id": str(receipt_id),
        "category": str(category),
        "status": str(status),
        "observed_at": observed_at,
        "command": _redact(command),
        "observations": _redact(observations),
        "checks": checks,
    }
    if errors:
        return normalized, checks, errors
    return normalized, checks, []


def _repository_identity(observations: Mapping[str, object], errors: list[str]) -> list[dict[str, object]]:
    raw_repositories = observations.get("repositories")
    if not isinstance(raw_repositories, list):
        errors.append("source_identity: observations.repositories is required")
        return []
    identities: list[dict[str, object]] = []
    names: set[str] = set()
    for raw in raw_repositories:
        if not isinstance(raw, Mapping):
            errors.append("source_identity: repository entry is not an object")
            continue
        name = raw.get("name")
        commit = raw.get("commit")
        dirty = raw.get("dirty")
        dirty_digest = raw.get("dirty_digest")
        tree_digest = raw.get("tree_digest")
        if name not in {"astrid", "runtime"} or name in names:
            errors.append("source_identity: exactly one astrid and one runtime repository is required")
        if not isinstance(commit, str) or not _HEX40.fullmatch(commit):
            errors.append(f"source_identity: {name!r} commit is not an exact 40-character SHA")
        if not isinstance(dirty, bool):
            errors.append(f"source_identity: {name!r} dirty must be boolean")
        if not _valid_hash(dirty_digest):
            errors.append(f"source_identity: {name!r} dirty_digest is invalid")
        if not _valid_hash(tree_digest):
            errors.append(f"source_identity: {name!r} tree_digest is invalid")
        if isinstance(name, str):
            names.add(name)
        identities.append(
            {
                "name": str(name),
                "commit": str(commit),
                "dirty": dirty,
                "dirty_digest": str(dirty_digest),
                "tree_digest": str(tree_digest),
            }
        )
    if names != {"astrid", "runtime"}:
        errors.append("source_identity: repositories must contain astrid and runtime")
    return sorted(identities, key=lambda item: str(item["name"]))


def _digest_rows(
    observations: Mapping[str, object],
    key: str,
    category: str,
    errors: list[str],
) -> list[dict[str, object]]:
    rows = observations.get(key)
    if not isinstance(rows, list) or not rows:
        errors.append(f"{category}: observations.{key} is required and cannot be empty")
        return []
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append(f"{category}: {key} contains a non-object")
            continue
        digest = row.get("sha256")
        if not _valid_hash(digest):
            errors.append(f"{category}: {key} contains an invalid sha256")
        normalized.append({
            "name": str(row.get("name", row.get("id", "unnamed"))),
            "path": str(row.get("path", "<unspecified>")),
            "sha256": str(digest),
        })
    return sorted(normalized, key=lambda item: (str(item["name"]), str(item["path"])))


def _census(observations: Mapping[str, object], category: str, errors: list[str]) -> dict[str, object]:
    entries = observations.get("entries")
    unowned = observations.get("unowned")
    if not isinstance(entries, list) or not entries:
        errors.append(f"{category}: observations.entries is required and cannot be empty")
        entries = []
    if not isinstance(unowned, list):
        errors.append(f"{category}: observations.unowned is required")
        unowned = []
    if unowned:
        errors.append(f"{category}: unowned entries are present")
    normalized = []
    for row in entries:
        if not isinstance(row, Mapping):
            errors.append(f"{category}: census entry is not an object")
            continue
        if not str(row.get("owner", "")).strip() or not str(row.get("disposition", "")).strip():
            errors.append(f"{category}: every census entry needs owner and disposition")
        normalized.append(_redact(row))
    return {"entries": normalized, "unowned": _redact(unowned)}


def _category_records(
    receipt_records: Sequence[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {category: [] for category in REQUIRED_CATEGORIES}
    for record in receipt_records:
        grouped[str(record["category"])].append(record)
    for records in grouped.values():
        records.sort(key=lambda item: (str(item["receipt_id"]), str(item["observed_at"])))
    return grouped


def _record_check_index(
    receipt_records: Sequence[dict[str, object]],
    errors: list[str],
) -> dict[str, dict[str, object]]:
    index: dict[str, dict[str, object]] = {}
    for record in receipt_records:
        receipt_id = str(record["receipt_id"])
        for check in record["checks"]:
            check_id = str(check["id"])
            if check_id in index:
                errors.append(f"duplicate check receipt: {check_id}")
                continue
            index[check_id] = {
                "status": check["status"],
                "receipt_id": receipt_id,
                "artifacts": check["artifacts"],
                "observations": check["observations"],
            }
    return index


def _artifact_index(receipt_records: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for record in receipt_records:
        for check in record["checks"]:
            for artifact in check["artifacts"]:
                key = f"{artifact['path']}::{artifact['sha256']}"
                rows[key] = {
                    "path": artifact["path"],
                    "sha256": artifact["sha256"],
                    "kind": artifact["kind"],
                    "receipt_id": record["receipt_id"],
                    "check_id": check["id"],
                }
    return sorted(rows.values(), key=lambda item: (str(item["path"]), str(item["check_id"])))


def _receipt_index(receipt_paths: Sequence[Path], records: Sequence[dict[str, object]], evidence_dir: Path) -> list[dict[str, object]]:
    rows = []
    for path in receipt_paths:
        try:
            raw_digest: str | None = sha256_file(path)
        except OSError:
            raw_digest = None
        # Invalid files are still indexed; their digest lets a reviewer locate
        # the exact failed input without mistaking it for accepted evidence.
        record = next(
            (item for item in records if item.get("_source_path") == str(path.resolve())),
            None,
        )
        rows.append(
            {
                "path": _safe_relpath(path, evidence_dir),
                "sha256": raw_digest,
                "receipt_id": record["receipt_id"] if record else None,
                "category": record["category"] if record else None,
                "checks": sorted(str(item["id"]) for item in record["checks"]) if record else [],
            }
        )
    return sorted(rows, key=lambda item: str(item["path"]))


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _markdown(report: Mapping[str, object]) -> str:
    status = str(report["status"]).upper()
    lines = [
        "# Astrid Beta Stage 1",
        "",
        f"**Acceptance status: `{status}`**  ",
        "Machine report: [`acceptance.json`](acceptance.json)  ",
        f"Report hash: `{report['hashes']['report']}`",
        "",
        "This file is generated from hash-verified machine receipts. It is an index, not an independent claim of completion.",
        "",
        "## Release identity",
        "",
        "| Repository | Commit | Dirty | Dirty digest | Tree digest |",
        "| --- | --- | ---: | --- | --- |",
    ]
    repositories = report.get("repositories", [])
    for row in repositories:
        lines.append(
            f"| {row['name']} | `{row['commit']}` | `{str(row['dirty']).lower()}` | `{row['dirty_digest']}` | `{row['tree_digest']}` |"
        )
    if not repositories:
        lines.append("| _missing evidence_ | — | — | — | — |")
    lines.extend(["", "## Blocking checklist", "", "| Check | Status | Receipt | Verified artifacts |", "| --- | --- | --- | --- |"])
    checks = report.get("checks", {})
    for check_id in REQUIRED_CHECKS:
        row = checks.get(check_id, {}) if isinstance(checks, Mapping) else {}
        check_status = str(row.get("status", "blocked")).upper()
        receipt_id = row.get("receipt_id", "—")
        artifacts = row.get("artifacts", [])
        paths = ", ".join(f"`{item['path']}`" for item in artifacts) if isinstance(artifacts, list) else "—"
        lines.append(f"| `{check_id}` | **{check_status}** | `{receipt_id}` | {paths or '—'} |")
    lines.extend(["", "## Receipt and artifact index", ""])
    lines.append(f"- Receipt index hash: `{report['hashes']['receipt_index']}`")
    lines.append(f"- Artifact index hash: `{report['hashes']['artifact_index']}`")
    lines.append(f"- Redaction policy: `{report['redaction']['schema']}`")
    lines.append("")
    lines.append("### Evidence files")
    lines.append("")
    for row in report.get("receipt_index", []):
        lines.append(f"- `{row['path']}` — `{row['sha256']}`")
    if not report.get("receipt_index"):
        lines.append("- _No receipt files were found._")
    lines.extend(["", "## Gate disposition", ""])
    errors = report.get("errors", [])
    if errors:
        lines.append("The gate is not accepted. Recorded blockers:")
        lines.append("")
        for error in errors:
            lines.append(f"- `{error}`")
    else:
        lines.append("Every required check is backed by a verified receipt and retained artifact.")
    lines.append("")
    return "\n".join(lines)


def aggregate(
    evidence_dir: Path,
    output_dir: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, object], int]:
    """Aggregate one evidence bundle and write deterministic output files."""

    evidence_dir = evidence_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    errors: list[str] = []
    if not evidence_dir.is_dir():
        errors.append(f"evidence directory is missing: {evidence_dir.name}")
        receipt_paths: list[Path] = []
    else:
        receipt_paths = sorted(
            path
            for path in evidence_dir.rglob("*.json")
            if path.name not in {"acceptance.json", "acceptance-report.json"}
        )
    records: list[dict[str, object]] = []
    for path in receipt_paths:
        record, _checks, receipt_errors = _validate_receipt(path, evidence_dir=evidence_dir)
        if record is not None:
            record["_source_path"] = str(path.resolve())
            records.append(record)
        errors.extend(receipt_errors)
    receipt_ids = [str(record["receipt_id"]) for record in records]
    if len(set(receipt_ids)) != len(receipt_ids):
        errors.append("receipt_id values must be unique")
    groups = _category_records(records)
    for category in REQUIRED_CATEGORIES:
        if not groups[category]:
            errors.append(f"missing required receipt category: {category}")
    check_index = _record_check_index(records, errors)
    for check_id in REQUIRED_CHECKS:
        row = check_index.get(check_id)
        if row is None:
            errors.append(f"missing required check: {check_id}")
        elif row["status"] != "pass":
            errors.append(f"required check is not passing: {check_id}")
    # Any receipt-level fail/block is a gate error even if it happened to carry
    # no checklist row of its own.
    for record in records:
        if record["status"] != "pass":
            errors.append(f"receipt is not passing: {record['receipt_id']}")

    source_records = groups["source_identity"]
    repositories: list[dict[str, object]] = []
    if source_records:
        observations = source_records[0].get("observations")
        if isinstance(observations, Mapping):
            repositories = _repository_identity(observations, errors)
    dep_records = groups["dependency_locks"]
    dependency_locks: list[dict[str, object]] = []
    if dep_records and isinstance(dep_records[0].get("observations"), Mapping):
        dependency_locks = _digest_rows(dep_records[0]["observations"], "locks", "dependency_locks", errors)
    manifest_records = groups["source_manifests"]
    source_manifests: list[dict[str, object]] = []
    if manifest_records and isinstance(manifest_records[0].get("observations"), Mapping):
        source_manifests = _digest_rows(manifest_records[0]["observations"], "manifests", "source_manifests", errors)
    census: dict[str, object] = {}
    for category in ("authority_census", "capability_census"):
        category_records = groups[category]
        if category_records and isinstance(category_records[0].get("observations"), Mapping):
            census[category] = _census(category_records[0]["observations"], category, errors)
        else:
            census[category] = {"entries": [], "unowned": []}

    receipt_index = _receipt_index(receipt_paths, records, evidence_dir)
    artifact_index = _artifact_index(records)
    # Exclude the private locator used while building the index.
    public_records = [{key: value for key, value in record.items() if not key.startswith("_")} for record in records]
    public_records.sort(key=lambda item: str(item["receipt_id"]))
    observed_times = [str(record["observed_at"]) for record in records if record.get("observed_at")]
    generated_at = max(observed_times) if observed_times else None
    report: dict[str, object] = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "pass" if not errors else ("blocked" if any("missing" in error or "required" in error for error in errors) else "fail"),
        "ok": not errors,
        "generated_at": generated_at,
        "normative_source": "reigh-app/docs/local-runtime/01-astrid-beta.md",
        "normative_sections": ["10", "11", "12", "13"],
        "repositories": repositories,
        "dependency_locks": dependency_locks,
        "source_manifests": source_manifests,
        "censuses": census,
        "receipts": public_records,
        "receipt_index": receipt_index,
        "artifact_index": artifact_index,
        "checks": check_index,
        "required_categories": list(REQUIRED_CATEGORIES),
        "required_checks": list(REQUIRED_CHECKS),
        "errors": sorted(set(errors)),
        "redaction": {
            "schema": REDACTION_VERSION,
            "secrets": "key-shaped values, bearer credentials, and secret assignments are redacted",
            "paths": "user-home path components are redacted; retained artifact links are evidence-root relative",
        },
        "provenance": {
            "evidence_dir": "<evidence-bundle>",
            "repo_root": repo_root.name,
            "no_live_receipts_created": True,
        },
    }
    report["hashes"] = {
        "receipt_index": sha256_bytes(canonical_json(receipt_index)),
        "artifact_index": sha256_bytes(canonical_json(artifact_index)),
    }
    report_for_hash = dict(report)
    report_for_hash["hashes"] = dict(report["hashes"])
    report_for_hash["hashes"]["report"] = "<self>"
    report_hash = sha256_bytes(canonical_json(report_for_hash))
    report["hashes"]["report"] = report_hash
    report_path = output_dir / "acceptance.json"
    markdown_path = output_dir / "ASTRID-BETA.md"
    markdown = _markdown(report)
    _write_atomic(report_path, canonical_json(report))
    _write_atomic(markdown_path, markdown.encode("utf-8"))
    return report, 0 if report["ok"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate hash-linked Astrid Stage 1 evidence.")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report, exit_code = aggregate(args.evidence_dir, args.output_dir, repo_root=args.repo_root)
    print(json.dumps({"status": report["status"], "ok": report["ok"], "report": str(args.output_dir / "acceptance.json"), "hash": report["hashes"]["report"]}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
