"""Release dependency-lock and toolchain evidence contract."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import pytest

from scripts.reshape.release_reproducibility import (
    ReproducibilityError,
    record_required_toolchain,
    validate_dependency_locks,
    validate_hashed_lock,
    validate_playwright,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

RUNAWAY_RELEASE_FIXTURE_HASHES = {
    "audio-reactive-v1.json": "e53d67df26c96d03967f7e2e620bd897ab004bfe45e8451e7ce67c6fc0cb5b8e",
    "timing-manifest.json": "eba9e6a521200bb57458111315ecb0314a31739980da72b44dac4d66d0fcacf6",
}


def test_repository_dependency_locks_are_hashed_exact_and_cover_metadata() -> None:
    report = validate_dependency_locks(REPO_ROOT)
    assert report["schema"] == "astrid.dependency_locks.v1"
    assert set(report["locks"]) == {
        "requirements/build.lock",
        "requirements/runtime.lock",
        "requirements/proof.lock",
    }
    assert report["locks"]["requirements/build.lock"]["packages"] >= 6
    assert report["locks"]["requirements/runtime.lock"]["packages"] >= 60
    assert report["locks"]["requirements/proof.lock"]["packages"] >= 70
    assert all(
        len(lock["sha256"]) == 64 for lock in report["locks"].values()
    )


def test_lock_validation_fails_closed_on_ranges_urls_and_missing_hashes(
    tmp_path: Path,
) -> None:
    for body, match in (
        ("example>=1\n", "exact == pin"),
        ("example @ https://example.invalid/a.whl\n", "exact == pin"),
        ("example==1\n", "no sha256 hash"),
    ):
        lock = tmp_path / "bad.lock"
        lock.write_text(body, encoding="utf-8")
        with pytest.raises(ReproducibilityError, match=match):
            validate_hashed_lock(lock)


def test_playwright_package_and_browser_revision_are_lock_aligned() -> None:
    root = REPO_ROOT / "scripts/reshape/editor_browser_smoke"
    report = validate_playwright(root)
    assert report["package_version"] == "1.62.1"
    assert len(report["package_lock_sha256"]) == 64
    browsers = root / "node_modules/playwright-core/browsers.json"
    if browsers.is_file():
        assert report["chromium"]["revision"]
        assert report["chromium"]["browserVersion"]


def test_required_release_toolchain_is_present_and_version_recorded() -> None:
    expected = ".".join(platform.python_version_tuple()[:2])
    report = record_required_toolchain(
        repo_root=REPO_ROOT,
        expected_python=expected,
        playwright_root=REPO_ROOT / "scripts/reshape/editor_browser_smoke",
    )
    assert report["python"]["version"] == platform.python_version()
    assert set(report["tools"]) == {"make", "bash", "git", "ffmpeg", "ffprobe"}
    assert all(item["version"] and item["executable"] for item in report["tools"].values())


def test_release_ci_enforces_hashed_build_runtime_and_toolchain_evidence() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--require-hashes -r requirements/build.lock" in workflow
    assert "-r requirements/runtime.lock" in workflow
    assert "python -m build --wheel --no-isolation" in workflow
    assert "scripts.reshape.release_reproducibility" in workflow
    assert '"toolchain": json.loads(' in workflow


def test_playwright_lockfile_remains_valid_json() -> None:
    root = REPO_ROOT / "scripts/reshape/editor_browser_smoke"
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["playwright"] == "1.62.1"
    assert lock["packages"][""]["devDependencies"]["playwright"] == "1.62.1"


def test_runaway_release_migration_inputs_are_tracked_and_byte_pinned() -> None:
    fixture_root = REPO_ROOT / "tests/fixtures/runaway_release"
    assert {
        path.name for path in fixture_root.glob("*.json")
    } == set(RUNAWAY_RELEASE_FIXTURE_HASHES)
    for name, expected_hash in RUNAWAY_RELEASE_FIXTURE_HASHES.items():
        fixture = fixture_root / name
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == expected_hash
