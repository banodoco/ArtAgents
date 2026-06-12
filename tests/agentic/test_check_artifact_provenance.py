from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.agentic.checks.artifact_provenance import c2_artifact_provenance


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _produces_event(
    *,
    plan_step_path: list[str],
    produces_name: str,
    data: bytes,
    step_version: int | None = 1,
    use_identity_cas: bool = False,
) -> dict:
    event = {
        "kind": "produces_check_passed",
        "plan_step_path": plan_step_path,
        "produces_name": produces_name,
        "ts": "2025-01-01T00:00:00Z",
    }
    digest = _sha256_bytes(data)
    if use_identity_cas:
        event["cas_identity_sha256"] = digest
    else:
        event["cas_sha256"] = digest
    if step_version is not None:
        event["step_version"] = step_version
    return event


def _write_produces_file(
    evidence_dir: Path,
    *,
    run_id: str = "run-1",
    step_path: tuple[str, ...] = ("build",),
    step_version: int = 1,
    produces_name: str = "output.txt",
    data: bytes = b"hello\n",
) -> Path:
    target = (
        evidence_dir
        / "runs"
        / run_id
        / "steps"
        / Path(*step_path)
        / f"v{step_version}"
        / "produces"
        / produces_name
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def test_c2_returns_na_when_no_events_or_produces_files_exist(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c2_artifact_provenance(evidence_dir)

    assert result["id"] == "C2"
    assert result["status"] == "na"


def test_c2_passes_for_matching_event_and_frozen_file(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    data = b"artifact bytes\n"
    _write_produces_file(evidence_dir, data=data)
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", data=data)],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 1
    assert result["detail"]["mismatches"] == []


def test_c2_passes_for_nested_step_path_and_non_default_version(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    data = b"nested artifact\n"
    _write_produces_file(
        evidence_dir,
        step_path=("compose", "build"),
        step_version=2,
        produces_name="final.mp4",
        data=data,
    )
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [
            _produces_event(
                plan_step_path=["compose", "build"],
                produces_name="final.mp4",
                step_version=2,
                data=data,
            )
        ],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 1


def test_c2_defaults_missing_step_version_to_v1(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    data = b"default version\n"
    _write_produces_file(evidence_dir, step_version=1, data=data)
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", step_version=None, data=data)],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 1


def test_c2_fails_for_orphan_event_without_matching_file(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="missing.txt", data=b"missing")],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "orphan_event"
    assert mismatch["key"]["produces_name"] == "missing.txt"


def test_c2_fails_for_orphan_file_without_matching_event(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    _write_produces_file(evidence_dir, data=b"orphan\n")

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "orphan_file"
    assert mismatch["key"]["produces_name"] == "output.txt"


def test_c2_fails_for_hash_mismatch(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    _write_produces_file(evidence_dir, data=b"actual\n")
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", data=b"expected\n")],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "hash_mismatch"
    assert mismatch["event_cas_sha256"] != mismatch["file_sha256"]


def test_c2_fails_for_invalid_produces_event_payload(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [{"kind": "produces_check_passed", "plan_step_path": ["build"], "produces_name": "x.txt"}],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "invalid_event"
    assert "cas_sha256" in mismatch["error"]


def test_c2_passes_for_identity_cas_event_with_cas_entry_and_symlink(tmp_path: Path) -> None:
    """Identity CAS events validate via .cas/<key> existence + symlink target,
    not by comparing the identity key to artifact bytes."""
    evidence_dir = tmp_path / "evidence"
    data = b"identity-keyed artifact\n"
    produces_path = _write_produces_file(evidence_dir, data=data)

    identity_key = _sha256_bytes(data)  # used as the identity key for test
    cas_dir = evidence_dir / ".cas"
    cas_dir.mkdir(parents=True, exist_ok=True)
    cas_entry = cas_dir / identity_key
    # Move the artifact bytes into .cas/<key> and symlink the produces path back.
    produces_path.rename(cas_entry)
    import os as _os
    _os.symlink(
        _os.path.relpath(str(cas_entry), str(produces_path.parent)),
        str(produces_path),
    )

    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [
            _produces_event(
                plan_step_path=["build"],
                produces_name="output.txt",
                data=data,
                use_identity_cas=True,
            )
        ],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 1
    assert result["detail"]["mismatches"] == []


def test_c2_fails_for_identity_cas_event_missing_cas_entry(tmp_path: Path) -> None:
    """When an identity CAS event references a key with no .cas/<key> entry,
    provenance reports a missing_cas_entry mismatch."""
    evidence_dir = tmp_path / "evidence"
    data = b"identity-keyed artifact\n"
    _write_produces_file(evidence_dir, data=data)
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [
            _produces_event(
                plan_step_path=["build"],
                produces_name="output.txt",
                data=data,
                use_identity_cas=True,
            )
        ],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "missing_cas_entry"
    assert "cas_identity_sha256" in mismatch


def test_c2_fails_for_identity_cas_event_not_a_symlink(tmp_path: Path) -> None:
    """When .cas/<key> exists but the produces path is a regular file
    instead of a symlink, provenance reports identity_not_symlink."""
    evidence_dir = tmp_path / "evidence"
    data = b"identity-keyed artifact\n"
    _write_produces_file(evidence_dir, data=data)

    identity_key = _sha256_bytes(data)
    cas_dir = evidence_dir / ".cas"
    cas_dir.mkdir(parents=True, exist_ok=True)
    (cas_dir / identity_key).write_bytes(data)  # .cas entry exists
    # produces path is NOT a symlink — it's a separate regular file

    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [
            _produces_event(
                plan_step_path=["build"],
                produces_name="output.txt",
                data=data,
                use_identity_cas=True,
            )
        ],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert mismatch["kind"] == "identity_not_symlink"


def test_c2_separates_same_step_and_name_across_runs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    data_one = b"run one\n"
    data_two = b"run two\n"
    _write_produces_file(evidence_dir, run_id="run-1", data=data_one)
    _write_produces_file(evidence_dir, run_id="run-2", data=data_two)
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", data=data_one)],
    )
    _write_jsonl(
        evidence_dir / "runs" / "run-2" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", data=data_two)],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 2


def test_c2_ignores_run_json_hashes_and_uses_frozen_file_bytes(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    data = b"trusted bytes\n"
    _write_produces_file(evidence_dir, data=data)
    (evidence_dir / "runs" / "run-1" / "run.json").write_text(
        json.dumps({"artifacts": {"output.txt": {"sha256": "0" * 64}}}),
        encoding="utf-8",
    )
    _write_jsonl(
        evidence_dir / "runs" / "run-1" / "events.jsonl",
        [_produces_event(plan_step_path=["build"], produces_name="output.txt", data=data)],
    )

    result = c2_artifact_provenance(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["matched"] == 1
