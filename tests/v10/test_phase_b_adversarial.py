"""Adversarial checks for the Phase-B setup and single-writer seams."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from astrid.core.model_setup.journal import (
    SetupJournal,
    SetupJournalError,
    artifact_path,
    journal_path,
    resolve_boot_state,
    staged_path,
)
from astrid.core.model_setup.manifest import ManifestError, make_manifest, save_manifest
from astrid.core.model_setup.repair import doctor_setup
from astrid.core.store.writer import DatabaseWriter, WriterSidecarError


def _insert_project(session, project_id: str) -> None:
    session.execute(
        "INSERT INTO projects (id, slug, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (project_id, project_id, project_id, "2026-08-15T00:00:00Z", "2026-08-15T00:00:00Z"),
    )


def test_wal_replacement_during_callback_is_not_adopted_as_new_baseline(
    tmp_path: Path, core_registry
) -> None:
    """A close racing a callback must fail closed after callback execution too."""
    db_path = tmp_path / "writer.sqlite3"
    writer = DatabaseWriter(db_path, core_registry)
    try:
        writer.submit(lambda session: _insert_project(session, "before"))
        entered = threading.Event()
        release = threading.Event()

        def callback(session) -> None:
            entered.set()
            # The main thread owns release in a try/finally below. Do not add
            # a shorter competing deadline here: this test runs immediately
            # after the fault matrix has spawned and killed 100+ processes,
            # so process startup can legitimately exceed ten seconds on a
            # loaded CI host. The suite-level timeout remains the deadlock
            # fence, and the finally block always releases this callback.
            release.wait()
            _insert_project(session, "during")

        outcome: list[BaseException] = []

        def submit_callback() -> None:
            try:
                writer.submit(callback)
            except BaseException as exc:  # noqa: BLE001 - assertion capture
                outcome.append(exc)

        thread = threading.Thread(target=submit_callback)
        thread.start()
        assert entered.wait(60), "writer callback did not start within 60 seconds"
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sqlite3, sys; c=sqlite3.connect(sys.argv[1]); c.execute('SELECT 1').fetchone(); c.close()",
                str(db_path),
            ],
            check=True,
            timeout=60,
        )
        # SQLite builds differ on whether a foreign close unlinks a WAL while
        # another connection is in a callback. Force the same inode replacement
        # that a backup/restore tool can perform after that close.
        wal_path = Path(f"{db_path}-wal")
        replacement = wal_path.with_suffix(".replacement")
        replacement.write_bytes(wal_path.read_bytes())
        replacement.replace(wal_path)
        release.set()
        thread.join(60)
        assert not thread.is_alive(), "writer callback did not finish within 60 seconds"
        assert len(outcome) == 1
        assert isinstance(outcome[0], WriterSidecarError)
        with pytest.raises(WriterSidecarError):
            writer.submit(lambda session: _insert_project(session, "after"))
    finally:
        release.set()
        writer.close()


def test_replay_marks_complete_bad_fields_and_schema_corrupt(tmp_path: Path) -> None:
    journal = SetupJournal(tmp_path)
    journal.append("bundle", "installed", sha256="a" * 64, size=3)
    path = journal_path(tmp_path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records.append({"schema": "astrid.setup_journal.v1", "artifact": "bundle", "event": "downloading", "offset": "oops"})
    records.append({"schema": "wrong", "artifact": "bundle", "event": "absent"})
    path.write_text("".join(json.dumps(record) + "\n" for record in records))

    snapshot = journal.replay()
    assert snapshot.corrupt is True
    assert snapshot.states["bundle"].phase == "installed"


def test_doctor_repairs_corrupt_bytes_after_journal_reconciliation(tmp_path: Path) -> None:
    content = b"signed payload"
    manifest = make_manifest(
        "bundle", version="1", content=content,
        license_identity="Apache-2.0", license_text=b"license",
    )
    manifest_dir = tmp_path / ".astrid" / "setup" / "manifests"
    manifest_dir.mkdir(parents=True)
    save_manifest(manifest, manifest_dir / "bundle.json")
    target = artifact_path(tmp_path, "bundle")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"tampered")
    journal = SetupJournal(tmp_path)
    journal.append("bundle", "installed", sha256=hashlib.sha256(content).hexdigest(), size=len(content))
    journal_path(tmp_path).write_bytes(b"not-json\n" + journal_path(tmp_path).read_bytes())

    def acquire(_manifest) -> None:
        target.write_bytes(content)

    reports = doctor_setup(tmp_path, acquire=acquire)
    assert [(report.artifact_id, report.verdict) for report in reports] == [("bundle", "repaired")]
    assert target.read_bytes() == content
    assert resolve_boot_state(tmp_path, write=False).states["bundle"].phase == "installed"


def test_doctor_does_not_call_a_noop_repair_success(tmp_path: Path) -> None:
    content = b"signed payload"
    manifest = make_manifest(
        "bundle", version="1", content=content,
        license_identity="Apache-2.0", license_text=b"license",
    )
    manifest_dir = tmp_path / ".astrid" / "setup" / "manifests"
    manifest_dir.mkdir(parents=True)
    save_manifest(manifest, manifest_dir / "bundle.json")
    target = artifact_path(tmp_path, "bundle")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"tampered")
    SetupJournal(tmp_path).append("bundle", "installed", sha256=hashlib.sha256(content).hexdigest(), size=len(content))

    reports = doctor_setup(tmp_path, acquire=lambda _manifest: None)
    assert reports[0].verdict == "repair_failed"


def test_boot_does_not_promote_staged_bytes_without_expected_metadata(tmp_path: Path) -> None:
    staged = staged_path(tmp_path, "bundle")
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"unverified")
    SetupJournal(tmp_path).append("bundle", "verifying")

    state = resolve_boot_state(tmp_path, write=False).states["bundle"]
    assert (state.phase, state.reason) == ("corrupt", "staged_metadata_missing")
    assert not artifact_path(tmp_path, "bundle").exists()


@pytest.mark.parametrize("artifact_id", ["../escape", "nested/id", r"nested\\id", "/absolute", ""])
def test_manifest_rejects_artifact_path_escape(artifact_id: str) -> None:
    with pytest.raises(ManifestError):
        make_manifest(
            artifact_id, version="1", content=b"x",
            license_identity="Apache-2.0", license_text=b"license",
        )
    with pytest.raises(SetupJournalError):
        artifact_path(Path("/tmp/root"), artifact_id)
