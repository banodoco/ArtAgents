"""Focused tests for the final Stage 1 evidence aggregator.

These tests deliberately build receipts in a temporary evidence bundle. They
do not call launch, migration, network, or render commands: the aggregator is
required to consume those receipts, never manufacture them.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.reshape.stage1_acceptance import (
    ACCEPTANCE_SCHEMA,
    CHECK_CATEGORY,
    RECEIPT_SCHEMA,
    REQUIRED_CATEGORIES,
    aggregate,
    canonical_json,
    sha256_bytes,
)


def _artifact(tmp_path: Path) -> tuple[str, str]:
    path = tmp_path / "trace.txt"
    path.write_text("real retained evidence\n", encoding="utf-8")
    return "trace.txt", sha256_bytes(path.read_bytes())


def _observations(category: str) -> dict[str, object]:
    if category == "source_identity":
        return {
            "evidence_mode": "automated",
            "repositories": [
                {
                    "name": "astrid",
                    "commit": "a" * 40,
                    "dirty": False,
                    "dirty_digest": "sha256:" + "1" * 64,
                    "tree_digest": "sha256:" + "2" * 64,
                    "root": "/Users/private/Astrid",
                },
                {
                    "name": "runtime",
                    "commit": "b" * 40,
                    "dirty": True,
                    "dirty_digest": "sha256:" + "3" * 64,
                    "tree_digest": "sha256:" + "4" * 64,
                    "root": "/Users/private/runtime",
                },
            ],
        }
    if category == "dependency_locks":
        return {
            "evidence_mode": "automated",
            "locks": [{"name": "python", "path": "requirements.lock", "sha256": "sha256:" + "5" * 64}],
        }
    if category == "source_manifests":
        return {
            "evidence_mode": "automated",
            "manifests": [{"name": "astrid-capabilities", "path": "capabilities.json", "sha256": "sha256:" + "6" * 64}],
        }
    if category in {"authority_census", "capability_census"}:
        return {
            "evidence_mode": "automated",
            "entries": [{"id": category, "owner": "runtime", "disposition": "accepted"}],
            "unowned": [],
        }
    result: dict[str, object] = {
        "evidence_mode": "live" if category in {"cold_launch", "render", "second_client", "migration", "backup_restore", "rollback", "doctor", "security", "network", "filesystem"} else "automated",
        "probe": f"verified {category}",
    }
    if category == "render":
        result.update({"remotion": {"status": "pass", "version": "pinned"}, "ffmpeg": {"status": "pass", "version": "pinned"}})
    if category == "second_client":
        result.update({"fixture": "second-client-core-v1.yaml", "actor": "fake-typescript-product", "no_astrid_types": True})
    if category == "migration":
        result.update({"dry_run": "pass", "final": "pass", "activation": "pass", "reconciliation": "pass"})
    if category == "backup_restore":
        result.update({"snapshot": "pass", "restore": "pass", "hashes_verified": True})
    if category == "rollback":
        result.update({"rollback_archive": "pass", "recovery": "pass"})
    return result


def _write_bundle(tmp_path: Path, *, mutate: dict[str, object] | None = None) -> Path:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    artifact_path, digest = _artifact(evidence)
    by_category: dict[str, list[str]] = {category: [] for category in REQUIRED_CATEGORIES}
    for check_id, category in CHECK_CATEGORY.items():
        by_category[category].append(check_id)
    for ordinal, category in enumerate(REQUIRED_CATEGORIES):
        payload: dict[str, object] = {
            "schema": RECEIPT_SCHEMA,
            "receipt_id": f"receipt-{ordinal:02d}-{category}",
            "category": category,
            "status": "pass",
            "observed_at": "2026-09-01T12:00:00Z",
            "command": ["lane", category],
            "observations": _observations(category),
            "checks": [
                {
                    "id": check_id,
                    "status": "pass",
                    "observations": {"assertions": [check_id], "result": "observed"},
                    "artifacts": [{"path": artifact_path, "sha256": digest, "kind": "retained-trace"}],
                }
                for check_id in sorted(by_category[category])
            ],
        }
        if mutate and category in mutate:
            update = mutate[category]
            if isinstance(update, dict):
                payload.update(update)
        (evidence / f"{ordinal:02d}-{category}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return evidence


def test_complete_bundle_is_accepted_and_hash_deterministic(tmp_path: Path) -> None:
    evidence = _write_bundle(tmp_path)
    out_one = tmp_path / "out-one"
    out_two = tmp_path / "out-two"
    first, first_exit = aggregate(evidence, out_one)
    second, second_exit = aggregate(evidence, out_two)

    assert first_exit == second_exit == 0
    assert first["schema"] == ACCEPTANCE_SCHEMA
    assert first["status"] == "pass"
    assert first["ok"] is True
    assert first["hashes"]["report"] == second["hashes"]["report"]
    assert json.loads((out_one / "acceptance.json").read_text()) == json.loads((out_two / "acceptance.json").read_text())
    markdown = (out_one / "ASTRID-BETA.md").read_text(encoding="utf-8")
    assert "ACCEPTANCE STATUS" not in markdown
    assert "**Acceptance status: `PASS`**" in markdown
    assert "a" * 40 in markdown and "b" * 40 in markdown
    assert "/Users/private" not in markdown
    assert "[REDACTED]" not in markdown
    assert first["censuses"]["authority_census"]["unowned"] == []


def test_missing_bundle_writes_blocked_outputs_and_never_passes(tmp_path: Path) -> None:
    report, exit_code = aggregate(tmp_path / "does-not-exist", tmp_path / "out")
    assert exit_code == 1
    assert report["status"] == "blocked"
    assert report["ok"] is False
    assert report["errors"]
    assert "missing required receipt category" in "\n".join(report["errors"])
    assert (tmp_path / "out" / "acceptance.json").is_file()
    assert "BLOCKED" in (tmp_path / "out" / "ASTRID-BETA.md").read_text(encoding="utf-8")


def test_missing_artifact_and_synthetic_render_are_blocking(tmp_path: Path) -> None:
    evidence = _write_bundle(
        tmp_path,
        mutate={
            "render": {"observations": {"evidence_mode": "synthetic"}},
        },
    )
    # Remove the shared retained artifact; every check must fail closed.
    (evidence / "trace.txt").unlink()
    report, exit_code = aggregate(evidence, tmp_path / "out")
    assert exit_code == 1
    assert report["status"] == "blocked"
    errors = "\n".join(report["errors"])
    assert "artifact is missing" in errors
    assert "synthetic/narrative evidence" in errors


def test_source_identity_and_census_are_strict(tmp_path: Path) -> None:
    evidence = _write_bundle(tmp_path)
    source_path = evidence / "00-source_identity.json"
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["observations"]["repositories"][0]["commit"] = "short"
    payload["observations"]["repositories"][1]["dirty_digest"] = "not-a-hash"
    authority_path = evidence / "04-authority_census.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["observations"]["unowned"] = ["legacy-writer"]
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    report, exit_code = aggregate(evidence, tmp_path / "out")
    assert exit_code == 1
    assert report["status"] in {"blocked", "fail"}
    errors = "\n".join(report["errors"])
    assert "exact 40-character SHA" in errors
    assert "dirty_digest is invalid" in errors
    assert "unowned entries are present" in errors


def test_receipt_and_artifact_indexes_are_sorted_and_hash_linked(tmp_path: Path) -> None:
    evidence = _write_bundle(tmp_path)
    report, _ = aggregate(evidence, tmp_path / "out")
    receipt_index = report["receipt_index"]
    artifact_index = report["artifact_index"]
    assert receipt_index == sorted(receipt_index, key=lambda row: row["path"])
    assert artifact_index == sorted(artifact_index, key=lambda row: (row["path"], row["check_id"]))
    assert report["hashes"]["receipt_index"] == sha256_bytes(canonical_json(receipt_index))
    assert report["hashes"]["artifact_index"] == sha256_bytes(canonical_json(artifact_index))
    report_without_hash = dict(report)
    report_without_hash["hashes"] = dict(report["hashes"])
    report_without_hash["hashes"]["report"] = "<self>"
    assert report["hashes"]["report"] == sha256_bytes(canonical_json(report_without_hash))
