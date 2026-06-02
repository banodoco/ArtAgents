"""C2 — artifact provenance check over frozen produces evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tests.agentic.checks.io import FrozenEvidencePack
from tests.agentic.checks.results import ScoredCheckResult, build_check_result


ArtifactKey = tuple[str, tuple[str, ...], int, str]


def c2_artifact_provenance(
    evidence_dir: Path | str | FrozenEvidencePack,
) -> ScoredCheckResult:
    """Join frozen produces files to produces_check_passed events."""
    pack = evidence_dir if isinstance(evidence_dir, FrozenEvidencePack) else FrozenEvidencePack(evidence_dir)
    event_records, event_refs, event_failures = _collect_event_records(pack)
    file_records, file_refs, file_failures = _collect_file_records(pack)

    if not event_records and not file_records and not event_failures and not file_failures:
        return build_check_result(
            "C2",
            "na",
            detail={"reason": "no produces_check_passed events or frozen produces files present"},
        )

    evidence_refs = _dedupe([*event_refs, *file_refs])
    mismatches: list[dict[str, Any]] = [*event_failures, *file_failures]

    all_keys = sorted(set(event_records) | set(file_records), key=_sort_key)
    matched = 0
    for key in all_keys:
        events = event_records.get(key, [])
        files = file_records.get(key, [])
        if len(events) > 1:
            mismatches.append(
                {
                    "kind": "duplicate_event",
                    "key": _render_key(key),
                    "events": [record["evidence_ref"] for record in events],
                }
            )
            continue
        if len(files) > 1:
            mismatches.append(
                {
                    "kind": "duplicate_file",
                    "key": _render_key(key),
                    "files": [record["evidence_ref"] for record in files],
                }
            )
            continue

        event = events[0] if events else None
        artifact = files[0] if files else None
        if event is None:
            mismatches.append(
                {
                    "kind": "orphan_file",
                    "key": _render_key(key),
                    "file": artifact["evidence_ref"],
                    "sha256": artifact["sha256"],
                }
            )
            continue
        if artifact is None:
            mismatches.append(
                {
                    "kind": "orphan_event",
                    "key": _render_key(key),
                    "event": event["evidence_ref"],
                    "cas_sha256": event["cas_sha256"],
                }
            )
            continue
        if event["cas_sha256"] != artifact["sha256"]:
            mismatches.append(
                {
                    "kind": "hash_mismatch",
                    "key": _render_key(key),
                    "event": event["evidence_ref"],
                    "file": artifact["evidence_ref"],
                    "event_cas_sha256": event["cas_sha256"],
                    "file_sha256": artifact["sha256"],
                }
            )
            continue
        matched += 1

    return build_check_result(
        "C2",
        "fail" if mismatches else "pass",
        evidence_refs=evidence_refs,
        detail={
            "events_seen": sum(len(records) for records in event_records.values()),
            "files_seen": sum(len(records) for records in file_records.values()),
            "matched": matched,
            "mismatches": mismatches,
        },
    )


def _collect_event_records(
    pack: FrozenEvidencePack,
) -> tuple[dict[ArtifactKey, list[dict[str, Any]]], list[str], list[dict[str, Any]]]:
    records: dict[ArtifactKey, list[dict[str, Any]]] = defaultdict(list)
    evidence_refs: list[str] = []
    failures: list[dict[str, Any]] = []

    for run_dir in pack.run_dirs():
        events_path = run_dir / "events.jsonl"
        rows = pack.read_jsonl(events_path)
        if rows is None:
            continue
        evidence_ref = pack.evidence_ref(events_path)
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or row.get("kind") != "produces_check_passed":
                continue
            evidence_refs.append(evidence_ref)
            try:
                key = _event_key(run_dir.name, row)
            except ValueError as exc:
                failures.append(
                    {
                        "kind": "invalid_event",
                        "event": evidence_ref,
                        "event_index": index,
                        "error": str(exc),
                    }
                )
                continue
            records[key].append(
                {
                    "evidence_ref": evidence_ref,
                    "event_index": index,
                    "cas_sha256": row["cas_sha256"],
                }
            )
    return records, evidence_refs, failures


def _collect_file_records(
    pack: FrozenEvidencePack,
) -> tuple[dict[ArtifactKey, list[dict[str, Any]]], list[str], list[dict[str, Any]]]:
    records: dict[ArtifactKey, list[dict[str, Any]]] = defaultdict(list)
    evidence_refs: list[str] = []
    failures: list[dict[str, Any]] = []

    for path in pack.glob_files("runs/*/steps/**/*"):
        rel = path.relative_to(pack.root)
        if "produces" not in rel.parts:
            continue
        try:
            key = _file_key(rel)
        except ValueError as exc:
            failures.append(
                {
                    "kind": "invalid_file",
                    "file": rel.as_posix(),
                    "error": str(exc),
                }
            )
            continue
        sha256 = pack.sha256_bytes(rel)
        if sha256 is None:
            failures.append(
                {
                    "kind": "invalid_file",
                    "file": rel.as_posix(),
                    "error": "could not read frozen file bytes",
                }
            )
            continue
        evidence_ref = rel.as_posix()
        evidence_refs.append(evidence_ref)
        records[key].append(
            {
                "evidence_ref": evidence_ref,
                "sha256": sha256,
            }
        )
    return records, evidence_refs, failures


def _event_key(run_id: str, event: dict[str, Any]) -> ArtifactKey:
    plan_step_path = event.get("plan_step_path")
    if not isinstance(plan_step_path, list) or not plan_step_path:
        raise ValueError("plan_step_path must be a non-empty list")
    step_segments = tuple(str(segment) for segment in plan_step_path if isinstance(segment, str) and segment)
    if len(step_segments) != len(plan_step_path):
        raise ValueError("plan_step_path elements must be non-empty strings")

    raw_version = event.get("step_version", 1)
    if not isinstance(raw_version, int) or isinstance(raw_version, bool) or raw_version < 1:
        raise ValueError("step_version must be an int >= 1")

    produces_name = event.get("produces_name")
    if not isinstance(produces_name, str) or not produces_name:
        raise ValueError("produces_name must be a non-empty string")

    cas_sha256 = event.get("cas_sha256")
    if not isinstance(cas_sha256, str) or not cas_sha256:
        raise ValueError("cas_sha256 must be a non-empty string")

    return (run_id, step_segments, raw_version, produces_name)


def _file_key(rel_path: Path) -> ArtifactKey:
    parts = rel_path.parts
    if len(parts) < 7 or parts[0] != "runs" or parts[2] != "steps":
        raise ValueError("file does not match runs/<run_id>/steps/... layout")

    try:
        produces_index = parts.index("produces")
    except ValueError as exc:
        raise ValueError("file is not under a produces directory") from exc

    if produces_index < 5:
        raise ValueError("produces path missing step path or version directory")
    version_part = parts[produces_index - 1]
    if not version_part.startswith("v") or not version_part[1:].isdigit():
        raise ValueError("version directory must be named v<int>")
    step_segments = tuple(parts[3 : produces_index - 1])
    if not step_segments:
        raise ValueError("produces path missing plan step path")

    return (
        parts[1],
        step_segments,
        int(version_part[1:] or "1"),
        rel_path.name,
    )


def _render_key(key: ArtifactKey) -> dict[str, Any]:
    run_id, step_segments, step_version, produces_name = key
    return {
        "run_id": run_id,
        "plan_step_path": list(step_segments),
        "step_version": step_version,
        "produces_name": produces_name,
    }


def _sort_key(key: ArtifactKey) -> tuple[str, str, int, str]:
    run_id, step_segments, step_version, produces_name = key
    return (run_id, "/".join(step_segments), step_version, produces_name)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
