"""Doctor integration coverage (m6 v10 rewrite).

The old runpod stale-handle / executor-registry doctor checks were removed in
the v10 rewrite. This module now asserts the new six-check doctor surface:

- ``sqlite_quick_check`` — read-only ``PRAGMA quick_check``;
- ``fk_integrity`` — ``PRAGMA foreign_key_check``;
- ``schema_versions`` — applied core + pack migrations vs the registry;
- ``media_paths`` — managed-media root and ``sha256/`` digest tree;
- ``data_paths`` — projects root and ``.astrid/`` accessibility;
- ``python_version`` — the Python 3.10+ floor.

plus the stable ``{"ok": bool, "state": str, "checks": [...],
"next_action": str | null}`` JSON envelope and fail-closed exit codes on a
missing/corrupt database.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path

from astrid.application import compose_standard_application
from astrid.core import doctor

V10_CHECK_NAMES = {
    "python_version",
    "data_paths",
    "media_paths",
    "sqlite_quick_check",
    "fk_integrity",
    "schema_versions",
}


def _fresh_project(root: Path) -> None:
    """Create a migrated database plus managed dirs under *root*."""
    with compose_standard_application(projects_root=root) as app:
        created = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert created.ok, created.error


def _capture(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = doctor.main(argv)
    return code, stdout.getvalue()


def test_doctor_reports_six_v10_checks() -> None:
    """run_checks returns exactly the six v10 checks, all ok on a fresh root."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fresh_project(root)
        checks = doctor.run_checks(projects_root=root)

    assert [c.name for c in checks] == [
        "python_version",
        "data_paths",
        "media_paths",
        "sqlite_quick_check",
        "fk_integrity",
        "schema_versions",
    ]
    assert {c.name for c in checks} == V10_CHECK_NAMES
    assert all(c.status == "ok" for c in checks)


def test_doctor_json_envelope_is_stable() -> None:
    """--json emits state and recovery guidance beside the six checks."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fresh_project(root)
        code, out = _capture(["--json", "--projects-root", str(root)])

    assert code == 0
    payload = json.loads(out)
    assert set(payload) == {"ok", "state", "checks", "next_action"}
    assert payload["ok"] is True
    assert payload["state"] == "ready"
    assert payload["next_action"] is None
    assert len(payload["checks"]) == 6
    for item in payload["checks"]:
        assert set(item) == {"name", "status", "detail", "required"}
        assert item["name"] in V10_CHECK_NAMES


def test_doctor_fails_closed_on_missing_database() -> None:
    """A missing DB yields exit 1 and ok=false without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".astrid").mkdir()
        checks = doctor.run_checks(projects_root=root)
        code, out = _capture(["--json", "--projects-root", str(root)])

    by_name = {c.name: c for c in checks}
    for name in ("sqlite_quick_check", "fk_integrity", "schema_versions"):
        assert by_name[name].status == "fail"
        # The missing-database diagnostic always carries the brand-new-root
        # guidance (informational only; the check still fails).
        assert "brand-new projects root" in by_name[name].detail
        assert "astrid projects create" in by_name[name].detail
    assert code == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert len(payload["checks"]) == 6


def test_doctor_fails_closed_on_corrupt_database() -> None:
    """A corrupt DB file yields exit 1 and ok=false without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".astrid").mkdir()
        (root / ".astrid" / "astrid.sqlite3").write_bytes(b"not a sqlite database")
        checks = doctor.run_checks(projects_root=root)
        code, out = _capture(["--json", "--projects-root", str(root)])

    by_name = {c.name: c for c in checks}
    for name in ("sqlite_quick_check", "fk_integrity", "schema_versions"):
        assert by_name[name].status == "fail"
    assert code == 1
    payload = json.loads(out)
    assert payload["ok"] is False
    assert len(payload["checks"]) == 6
