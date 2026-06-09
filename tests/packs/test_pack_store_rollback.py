"""Behavioral tests for InstalledPackStore — install, read, rollback.

Tests exercise the public API via real filesystem inputs/outputs with no
mocking of internals.  Caplog assertions verify the Step 7b routed swallow
sites in pack_store.py:

  * :424 — except TypeError (noqa-only, control-flow for malformed records)
  * :426-427 — except Exception → log_and_swallow(context="pack_store.load_record")

Target: ≥80% line coverage of astrid/core/pack_store.py.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.store import InstallRecord, InstalledPackStore


def _record(
    pack_id: str = "my.pack",
    packs_home: str | Path | None = None,
    *,
    revision: str | None = None,
) -> InstallRecord:
    install_root = str(Path(packs_home) / pack_id) if packs_home else f"/tmp/{pack_id}"
    rev = revision or pack_id
    return InstallRecord(
        pack_id=pack_id,
        name="My Pack",
        version="1.0.0",
        schema_version=2,
        source_path="/src/my_pack",
        installed_at="2024-01-01T00:00:00Z",
        revision=rev,
        install_root=install_root,
    )


class TestInstallAndRead:
    def test_record_install_and_get_active(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("my.pack", tmp_path)

        store.record_install(rec)

        # Symlink the active revision
        link = store.active_symlink_path("my.pack")
        link.parent.mkdir(parents=True, exist_ok=True)
        rev_dir = Path(rec.install_root) / "revisions" / rec.revision
        link.symlink_to(Path("revisions") / rec.revision)

        result = store.get_active("my.pack")
        assert result is not None
        assert result.pack_id == "my.pack"
        assert result.version == "1.0.0"
        assert result.name == "My Pack"

    def test_is_installed_true(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("pack.a", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("pack.a")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)
        assert store.is_installed("pack.a") is True

    def test_is_installed_false_when_not_present(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        assert store.is_installed("no.such.pack") is False

    def test_list_installed_empty_home(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        assert store.list_installed() == []

    def test_list_installed_returns_records(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        for pid in ("pack.a", "pack.b"):
            rec = _record(pid, tmp_path)
            store.record_install(rec)
            link = store.active_symlink_path(pid)
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(Path("revisions") / rec.revision)
        results = store.list_installed()
        ids = {r.pack_id for r in results}
        assert ids == {"pack.a", "pack.b"}

    def test_active_pack_roots_returns_resolved_dirs(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("pack.root", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("pack.root")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)
        roots = store.active_pack_roots()
        assert len(roots) == 1
        assert roots[0].is_dir()

    def test_get_active_returns_none_when_no_symlink(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("pack.nosym", tmp_path)
        store.record_install(rec)
        # No symlink created — active_revision_path returns None.
        assert store.get_active("pack.nosym") is None


class TestRollback:
    def _install_two_revisions(self, tmp_path: Path, pack_id: str = "my.pack"):
        """Install pack_id with revision v1 active, then add revision v2."""
        store = InstalledPackStore(packs_home=tmp_path)

        # Revision v1: the original active revision
        rev1_name = pack_id
        rec1 = _record(pack_id, tmp_path, revision=rev1_name)
        store.record_install(rec1)

        # Create and activate v1 symlink
        link = store.active_symlink_path(pack_id)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rev1_name)

        # Revision v2: a newer revision (not yet active)
        rev2_name = f"{pack_id}.20240202T120000Z"
        rec2 = InstallRecord(
            pack_id=pack_id,
            name="My Pack",
            version="2.0.0",
            schema_version=2,
            source_path="/src/my_pack_v2",
            installed_at="2024-02-02T12:00:00Z",
            revision=rev2_name,
            install_root=str(tmp_path / pack_id),
        )
        store.record_install(rec2)

        return store, rev1_name, rev2_name

    def test_rollback_switches_active_symlink(self, tmp_path: Path) -> None:
        store, rev1, rev2 = self._install_two_revisions(tmp_path)
        pack_id = "my.pack"

        # Activate v2 first via rollback_to_revision
        store.rollback_to_revision(pack_id, rev2)
        active = store.get_active(pack_id)
        assert active is not None
        assert active.revision == rev2
        assert active.version == "2.0.0"

        # Now rollback to v1
        store.rollback_to_revision(pack_id, rev1)
        active = store.get_active(pack_id)
        assert active is not None
        assert active.revision == rev1
        assert active.version == "1.0.0"

    def test_rollback_marks_old_revision_inactive(self, tmp_path: Path) -> None:
        store, rev1, rev2 = self._install_two_revisions(tmp_path)
        pack_id = "my.pack"

        store.rollback_to_revision(pack_id, rev2)

        # v1 is now marked inactive on disk
        old_rec = store._read_revision_record(pack_id, rev1)
        assert old_rec is not None
        assert old_rec.active is False

    def test_rollback_marks_target_revision_active(self, tmp_path: Path) -> None:
        store, rev1, rev2 = self._install_two_revisions(tmp_path)
        pack_id = "my.pack"

        store.rollback_to_revision(pack_id, rev2)
        new_rec = store._read_revision_record(pack_id, rev2)
        assert new_rec is not None
        assert new_rec.active is True

    def test_rollback_missing_revision_raises(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("pack.err", tmp_path)
        store.record_install(rec)
        with pytest.raises(AstridError, match="does not exist"):
            store.rollback_to_revision("pack.err", "nonexistent.rev")

    def test_rollback_noop_when_already_active(self, tmp_path: Path) -> None:
        store, rev1, rev2 = self._install_two_revisions(tmp_path)
        pack_id = "my.pack"

        # Already on rev1 — rollback to rev1 is a no-op
        store.rollback_to_revision(pack_id, rev1)
        active = store.get_active(pack_id)
        assert active is not None
        assert active.revision == rev1

    def test_no_partial_pack_remains_after_failed_rollback(self, tmp_path: Path) -> None:
        """Rollback to non-existent revision leaves the store unchanged."""
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("pack.stable", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("pack.stable")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)

        with pytest.raises(AstridError):
            store.rollback_to_revision("pack.stable", "bad.revision")

        # Active symlink still points to original revision
        active = store.get_active("pack.stable")
        assert active is not None
        assert active.revision == rec.revision


class TestRoutedSwallows:
    """Cover the Step 7b routed swallow sites in _read_active_record."""

    def test_malformed_json_returns_none(self, tmp_path: Path) -> None:
        """OSError / JSONDecodeError in the first read returns None (no log_and_swallow)."""
        store = InstalledPackStore(packs_home=tmp_path)
        pack_id = "broken.json"
        rev_dir = tmp_path / pack_id / "revisions" / pack_id
        astrid_dir = rev_dir / ".astrid"
        astrid_dir.mkdir(parents=True, exist_ok=True)
        (astrid_dir / "install.json").write_text("NOT JSON", encoding="utf-8")

        link = store.active_symlink_path(pack_id)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / pack_id)

        result = store.get_active(pack_id)
        assert result is None

    def test_type_error_from_dict_returns_none_noqa_site(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """TypeError in InstallRecord.from_dict returns None (noqa-only site :424)."""
        store = InstalledPackStore(packs_home=tmp_path)
        pack_id = "type.err"
        rev_dir = tmp_path / pack_id / "revisions" / pack_id
        astrid_dir = rev_dir / ".astrid"
        astrid_dir.mkdir(parents=True, exist_ok=True)
        # pack_id is required positional — omitting it triggers TypeError in from_dict
        data = {"name": "My Pack", "version": "1.0.0"}
        (astrid_dir / "install.json").write_text(json.dumps(data), encoding="utf-8")

        link = store.active_symlink_path(pack_id)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / pack_id)

        with caplog.at_level(logging.DEBUG):
            result = store.get_active(pack_id)

        assert result is None

    def test_unexpected_exception_routes_through_log_and_swallow(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unexpected Exception in from_dict routes to log_and_swallow (site :426-427)."""
        store = InstalledPackStore(packs_home=tmp_path)
        pack_id = "exc.route"
        rev_dir = tmp_path / pack_id / "revisions" / pack_id
        astrid_dir = rev_dir / ".astrid"
        astrid_dir.mkdir(parents=True, exist_ok=True)
        (astrid_dir / "install.json").write_text(
            json.dumps(_record(pack_id, tmp_path).to_dict()), encoding="utf-8"
        )

        link = store.active_symlink_path(pack_id)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / pack_id)

        boom = ValueError("synthetic schema error")
        monkeypatch.setattr(InstallRecord, "from_dict", staticmethod(lambda d: (_ for _ in ()).throw(boom)))

        with caplog.at_level(logging.DEBUG):
            result = store.get_active(pack_id)

        assert result is None
        assert any("pack_store.load_record" in r.message for r in caplog.records)


class TestRemoveAndMiscPaths:
    def test_remove_install_clears_everything(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("rem.pack", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("rem.pack")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)

        store.remove_install("rem.pack")
        assert not (tmp_path / "rem.pack").exists()

    def test_remove_install_keep_revisions(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("keep.pack", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("keep.pack")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)

        store.remove_install("keep.pack", keep_revisions=True)
        rev_dir = tmp_path / "keep.pack" / "revisions"
        assert rev_dir.is_dir()

    def test_list_installed_nonexistent_home(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path / "does_not_exist")
        assert store.list_installed() == []

    def test_active_pack_roots_nonexistent_home(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path / "does_not_exist")
        assert store.active_pack_roots() == ()

    def test_list_revisions_empty_when_no_revisions_dir(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        assert store.list_revisions("no.pack") == []

    def test_mark_inactive_removes_symlink(self, tmp_path: Path) -> None:
        store = InstalledPackStore(packs_home=tmp_path)
        rec = _record("inactive.pack", tmp_path)
        store.record_install(rec)
        link = store.active_symlink_path("inactive.pack")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("revisions") / rec.revision)

        store.mark_inactive("inactive.pack")
        assert not link.exists()
        assert store.get_active("inactive.pack") is None
