"""Focused contract tests for the m8 evidence boundary."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts.reshape import m8_gate
from scripts.reshape.m8_gate import (
    BLOCKING_EVIDENCE_CLASSES,
    EVIDENCE_CLASSES,
    EvidenceValidationError,
    GA_ITEM_SELECTOR_MAP,
    PublicationError,
    RELEASE_FILENAMES,
    SCHEMA,
    publish_release_artifacts,
    validate_evidence,
)


DIGEST = "a" * 64
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat()
REPO_ROOT = Path(__file__).resolve().parents[2]


def _record(schema: str = "astrid.m8.lane.v1", **extra):
    value = {
        "schema": schema,
        "status": "pass",
        "wheel_sha256": DIGEST,
        "started_at": STAMP,
        "finished_at": STAMP,
    }
    value.update(extra)
    return value


def _valid_bundle():
    bundle = {
        "schema": SCHEMA,
        "artifact_identity": _record(
            "astrid.installed_artifact.v1",
            import_path="/isolated/venv/lib/python3.11/site-packages/astrid/__init__.py",
        ),
        "matrix_lanes": [
            _record(os="Linux", python="3.11", browser="Chromium"),
            _record(os="Linux", python="3.12", browser="Chromium"),
        ],
        "authority_census": _record(scanned_files=["astrid/__init__.py"]),
        "catalog_migrations": _record(catalog_tables=14),
        "conformance": _record(selector="installed-journey:ga-item-2"),
        "crash_contention": _record(selector="installed-journey:ga-item-5"),
        "backup_restore": _record(selector="installed-journey:ga-item-9"),
        "clean_account": _record(selector="installed-journey:ga-item-10"),
        "performance": _record(
            report_only=True,
            budget_status="unresolved",
            budget_source=None,
            timing={"samples_ms": [1.0, 1.1, 1.2]},
            environment={
                "python": "3.11.0",
                "platform": "Linux",
                "system": "Linux",
                "machine": "x86_64",
            },
        ),
        "manual": _record(
            status="unresolved",
            blocking=False,
            owner="Astrid Release Owner",
            device="physical-macos-chromium",
        ),
    }
    return bundle


def test_ga_item_selector_map_is_complete():
    assert set(GA_ITEM_SELECTOR_MAP) == set(range(1, 13))
    assert all(item["installed_selector"] for item in GA_ITEM_SELECTOR_MAP.values())
    assert all(item["evidence_class"] in EVIDENCE_CLASSES for item in GA_ITEM_SELECTOR_MAP.values())
    assert not any(
        item["installed_selector"].startswith("tests/")
        for item in GA_ITEM_SELECTOR_MAP.values()
    )


def test_ci_declares_the_complete_blocking_m8_matrix_and_browser_lane():
    """Keep the workflow aligned with the frozen packaged release contract."""
    workflow_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    raw = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    jobs = workflow["jobs"]

    installed = jobs["m8-installed"]
    matrix = installed["strategy"]["matrix"]
    assert installed["runs-on"] == "${{ matrix.os }}"
    assert installed["strategy"]["fail-fast"] is False
    assert matrix["os"] == ["ubuntu-latest", "macos-latest"]
    assert matrix["python-version"] == ["3.11", "3.12"]
    assert matrix["browser"] == ["chromium"]

    # Every cell installs and executes the declared browser target.  The
    # actual macOS runner is explicit; CI never relabels Linux as macOS.
    assert "npx playwright install chromium" in raw
    assert "npx playwright install --with-deps chromium" in raw
    assert "npm run smoke" in raw
    assert "no Linux emulation or metadata-only observation is accepted" in raw


def test_ci_retains_m8_failure_evidence_and_blocks_publication_on_all_floors():
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    installed = jobs["m8-installed"]
    publication = jobs["m8-publication"]

    installed_steps = installed["steps"]
    upload_steps = [step for step in installed_steps if step.get("uses", "").startswith("actions/upload-artifact")]
    assert upload_steps and upload_steps[-1]["if"] == "always()"
    upload_path = upload_steps[-1]["with"]["path"]
    assert "m8-logs/**" in upload_path
    assert "m8-evidence/**" in upload_path
    assert "out/m8-gate/**" in upload_path
    assert "recordings/**" in upload_path

    assert set(publication["needs"]) == {
        "m8-artifact",
        "m8-installed",
        "python",
        "m4-gate",
        "m7-release-candidate",
    }
    publication_if = publication["if"]
    for job in ("m8-artifact", "m8-installed", "python", "m4-gate", "m7-release-candidate"):
        assert f"needs.{job}.result == 'success'" in publication_if
    assert "make m8-gate" in "\n".join(
        str(step.get("run", "")) for step in publication["steps"]
    )

    # Existing repository-wide, type, bridge, and factoring floors remain in
    # the workflow rather than being replaced by the packaged gate.
    assert "compare_ruff_baseline.py" in (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    assert "compare_mypy_baseline.py" in (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    assert "test_reigh_authority_absence.py" in (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    assert "test_pack_factoring.py" in (REPO_ROOT / ".github/workflows/ci.yml").read_text()


def test_m8_evidence_schema_preserves_blocking_and_manual_ownership():
    result = validate_evidence(_valid_bundle(), digest=DIGEST, now=NOW)
    assert result.ok
    assert result.blocking_records == len(BLOCKING_EVIDENCE_CLASSES) + 1
    assert result.manual_records == 1


def test_gate_rejects_stale_malformed_or_digest_mismatched_evidence():
    stale = _valid_bundle()
    stale["conformance"] = _record(
        wheel_sha256="b" * 64,
        started_at=(NOW - timedelta(days=2)).isoformat(),
        finished_at=(NOW - timedelta(days=2)).isoformat(),
    )
    with pytest.raises(EvidenceValidationError) as caught:
        validate_evidence(stale, digest=DIGEST, now=NOW)
    message = str(caught.value)
    assert "digest does not match" in message
    assert "stale" in message


def test_gate_rejects_source_only_provisional_and_retained_records():
    for label in ("source-only", "provisional", "retained"):
        bundle = _valid_bundle()
        bundle["authority_census"] = _record(label=label)
        with pytest.raises(EvidenceValidationError, match="disallowed"):
            validate_evidence(bundle, digest=DIGEST, now=NOW)


def test_release_publishes_all_six_documents_after_validation(tmp_path: Path):
    artifact_dir = tmp_path / "artifacts" / "m8"
    publication = publish_release_artifacts(
        _valid_bundle(),
        digest=DIGEST,
        artifact_dir=artifact_dir,
        diagnostics_dir=tmp_path / "out" / "m8-gate",
        now=NOW,
    )

    assert publication.digest == DIGEST
    assert tuple(path.name for path in publication.files) == RELEASE_FILENAMES
    assert all((artifact_dir / filename).is_file() for filename in RELEASE_FILENAMES)
    acceptance = json.loads((artifact_dir / "acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["status"] == "pass"
    assert acceptance["wheel_sha256"] == DIGEST
    assert "Status: SHIP" in (artifact_dir / "SHIP.md").read_text(encoding="utf-8")


def test_release_rejects_failed_lane_and_retains_diagnostic(tmp_path: Path):
    bundle = _valid_bundle()
    bundle["lanes"] = [_record(lane="installed-browser", status="failed", error="lane crashed")]
    artifact_dir = tmp_path / "artifacts" / "m8"
    diagnostics_dir = tmp_path / "out" / "m8-gate"

    with pytest.raises(EvidenceValidationError) as caught:
        publish_release_artifacts(
            bundle,
            digest=DIGEST,
            artifact_dir=artifact_dir,
            diagnostics_dir=diagnostics_dir,
            now=NOW,
        )

    assert "installed-browser" in str(caught.value)
    assert not artifact_dir.exists()
    diagnostic = diagnostics_dir / "failure.json"
    assert diagnostic.is_file()
    payload = json.loads(diagnostic.read_text(encoding="utf-8"))
    assert payload["published"] is False
    assert "lane crashed" in diagnostic.read_text(encoding="utf-8")


def test_release_rolls_back_partial_publication_and_keeps_diagnostic(tmp_path: Path, monkeypatch):
    artifact_dir = tmp_path / "artifacts" / "m8"
    diagnostics_dir = tmp_path / "out" / "m8-gate"
    real_replace = m8_gate.os.replace
    calls = {"count": 0}

    def fail_on_third_replace(source, destination):
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("injected publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(m8_gate.os, "replace", fail_on_third_replace)
    with pytest.raises(PublicationError, match="injected publication failure"):
        publish_release_artifacts(
            _valid_bundle(),
            digest=DIGEST,
            artifact_dir=artifact_dir,
            diagnostics_dir=diagnostics_dir,
            now=NOW,
        )

    assert not artifact_dir.exists()
    assert (diagnostics_dir / "failure.json").is_file()
    assert "injected publication failure" in (diagnostics_dir / "failure.json").read_text(
        encoding="utf-8"
    )
