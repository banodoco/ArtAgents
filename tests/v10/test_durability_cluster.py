"""Focused durability regressions for completion media and the live writer."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.core.io.media_import import (
    MediaLocationError,
    managed_media_path,
    prepare_media_file,
    publish_prepared_for_commit,
    set_media_crash_hook,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import WriterSidecarError
from tests.v10.test_crash_atomicity import _build_context


def _seed(tmp_path: Path):
    db_path = tmp_path / "astrid.sqlite3"
    managed_root = tmp_path / "managed"
    managed_root.mkdir()
    context = _build_context(db_path, managed_root=managed_root)
    UnitOfWork(context.writer).run(
        lambda u: context.projects.create(
            u,
            slug="durability-proj",
            name="Durability Project",
            settings={},
            idempotency_key="durability-project",
            project_id="durability-proj",
        )
    )
    source = managed_root / "input.svg"
    source.write_bytes(b"<svg>durability</svg>")
    return context, managed_root, source


def test_prepublished_import_is_stat_only_and_rejects_missing_bytes(
    tmp_path: Path,
) -> None:
    context, managed_root, source = _seed(tmp_path)
    try:
        prepared = prepare_media_file(source, root=managed_root)
        (publication,) = publish_prepared_for_commit(
            managed_root, "a" * 32, [prepared]
        )
        source.unlink()
        shutil.rmtree(managed_root / ".astrid" / "media" / ".staging")

        hooks: list[str] = []
        set_media_crash_hook(hooks.append)
        try:
            model = UnitOfWork(context.writer).run(
                lambda u: context.media.import_prepared(
                    u,
                    project_id="durability-proj",
                    prepared=prepared,
                    idempotency_key="prepublished-import",
                    media_id="media-durability",
                    published=publication,
                )
            )
        finally:
            set_media_crash_hook(None)
        assert model.content_hash == prepared.digest
        assert hooks == ["repo.published"]
        assert not source.exists()

        managed_media_path(managed_root, prepared.digest).unlink()
        with pytest.raises(MediaLocationError):
            UnitOfWork(context.writer).run(
                lambda u: context.media.import_prepared(
                    u,
                    project_id="durability-proj",
                    prepared=prepared,
                    idempotency_key="missing-published",
                    media_id="media-durability-missing",
                    published=publication,
                )
            )
    finally:
        context.writer.close()


def test_writer_fails_closed_after_foreign_wal_close(tmp_path: Path) -> None:
    context, _managed_root, _source = _seed(tmp_path)
    try:
        context.writer.submit(
            lambda session: session.execute(
                "INSERT INTO projects "
                "(id, slug, name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "durability-extra",
                    "durability-extra",
                    "Durability Extra",
                    "2026-08-24T00:00:00Z",
                    "2026-08-24T00:00:00Z",
                ),
            )
        )
        db_path = context.db_path
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as reader:
            reader.execute("SELECT COUNT(*) FROM projects").fetchone()
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sqlite3; "
                    f"c = sqlite3.connect({str(db_path)!r}); "
                    "c.execute('SELECT COUNT(*) FROM projects').fetchone(); "
                    "c.close()"
                ),
            ],
            check=True,
        )
        # Some SQLite/macOS builds retain the sidecar while another
        # connection is open; unlinking the test fixture models the same
        # replacement event deterministically.
        wal_path = Path(f"{db_path}-wal")
        if wal_path.exists():
            wal_path.unlink()

        with pytest.raises(WriterSidecarError):
            context.writer.submit(
                lambda session: session.execute(
                    "INSERT INTO projects "
                    "(id, slug, name, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        "after-poison",
                        "after-poison",
                        "After Poison",
                        "2026-08-24T00:00:00Z",
                        "2026-08-24T00:00:00Z",
                    ),
                )
            )
    finally:
        context.writer.close()
