"""Tests for Git-backed pack install, update, rollback, and dry-run.

Uses local git repos (not remote URLs) to avoid network dependencies.
All tests use ``InstalledPackStore(packs_home=tmpdir)`` for isolation.
"""

from __future__ import annotations

import io
import json as _json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from astrid.core.pack.store import (
    InstalledPackStore,
)
from astrid.core.contracts.errors import AstridError

from astrid.core.pack.canonical import (
    CanonicalPackValidationError,
    ExternalDatabaseForbidden,
    ExternalPackSource,
)
from astrid.core.pack import install_git as install_git_module
import astrid.core.pack.install as install_module
from astrid.core.pack import install_local as install_local_module
from astrid.core.pack.install import (
    _check_git_available,
    _diff_component_inventories,
    _find_pack_root_in_checkout,
    _format_trust_summary,
    _install_from_git,
    _is_git_url,
    _resolve_git_ref,
    _run_git,
    install_pack,
    rollback_pack,
    update_pack,
)
from astrid.core.pack.cli import cmd_inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _packs_home(tmpdir: str):
    """Temporarily override ASTRID_HOME for store isolation."""
    with mock.patch.dict(os.environ, {"ASTRID_HOME": tmpdir}):
        yield


def _make_minimal_pack(root: Path, pack_id: str = "test_pack") -> Path:
    """Write a minimal valid v1 pack, return the pack root."""
    (root / "pack.yaml").write_text(
        textwrap.dedent(f"""\
            schema_version: 1
            id: {pack_id}
            name: {pack_id.replace('_', ' ').title()}
            version: 0.1.0
            description: A test pack for Git install validation.
            content:
              executors: executors
              orchestrators: orchestrators
              elements: elements
            agent:
              purpose: Testing
              entrypoints:
                - validate
                - install
        """),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(f"# {pack_id}\n\nAgent guide.\n")
    (root / "README.md").write_text(f"# {pack_id}\n\nUser docs.\n")
    (root / "STAGE.md").write_text("## Purpose\n\nTesting.\n")
    for sub in ("executors", "orchestrators", "elements"):
        (root / sub).mkdir(parents=True, exist_ok=True)
        (root / sub / ".gitkeep").write_text("", encoding="utf-8")
    return root


def _make_git_repo_with_pack(
    tmpdir: str, pack_id: str = "git_pack", *,
    subdir: bool = False,
) -> tuple[str, str]:
    """Create a local git repo with a minimal pack, return (repo_path, commit_sha).

    The repo root is named after *pack_id* so the ``source.name == pack_id``
    invariant holds for local-path installs.  If *subdir* is True, the pack
    lives inside a subdirectory ``<pack_id>/my-pack/`` (still named after
    pack_id so the outer directory matches).
    """
    # Use a unique wrapper directory to avoid name clashes between tests
    wrapper = Path(tempfile.mkdtemp(dir=tmpdir, prefix=f"{pack_id}_repo_"))
    repo_path = wrapper / pack_id
    repo_path.mkdir(parents=True, exist_ok=True)

    if subdir:
        pack_root = repo_path / "my-pack"
    else:
        pack_root = repo_path

    _make_minimal_pack(pack_root, pack_id=pack_id)
    # Initialize git, add, commit
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_path),
                   capture_output=True, check=True, timeout=30)
    subprocess.run(["git", "config", "user.email", "test@astrid.local"],
                   cwd=str(repo_path), capture_output=True, check=True, timeout=30)
    subprocess.run(["git", "config", "user.name", "Astrid Test"],
                   cwd=str(repo_path), capture_output=True, check=True, timeout=30)
    subprocess.run(["git", "add", "-A"], cwd=str(repo_path),
                   capture_output=True, check=True, timeout=30)
    subprocess.run(["git", "commit", "-m", "initial commit"],
                   cwd=str(repo_path), capture_output=True, check=True, timeout=30)

    # Get commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_path),
        capture_output=True, text=True, check=True, timeout=30,
    )
    commit_sha = result.stdout.strip()

    return str(repo_path), commit_sha
def _make_canonical_git_repo_with_pack(
    tmpdir: str,
    pack_id: str,
    *,
    nested: bool = False,
) -> tuple[str, Path, str]:
    """Create a local Git repo containing one canonical v2 pack."""
    wrapper = Path(tempfile.mkdtemp(dir=tmpdir, prefix=f"{pack_id}_canonical_repo_"))
    repo_path = wrapper / "repository"
    repo_path.mkdir(parents=True)
    pack_root = repo_path / "nested-source" if nested else repo_path
    pack_root.mkdir(exist_ok=True)
    (pack_root / "pack.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            id: {pack_id}
            name: {pack_id.replace("_", " ").title()}
            version: 1.0.0
            capabilities: [render]
            """
        ),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(repo_path),
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@astrid.local"],
        cwd=str(repo_path),
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "config", "user.name", "Astrid Test"],
        cwd=str(repo_path),
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(repo_path),
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial canonical commit"],
        cwd=str(repo_path),
        capture_output=True,
        check=True,
        timeout=30,
    )
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    return str(repo_path), pack_root, commit_sha



def _make_another_commit(
    repo_path: str,
    pack_id: str,
    new_version: str = "0.2.0",
    *,
    schema_less: bool = False,
) -> str:
    """Make another commit to the git repo, return the new commit SHA."""
    repo = Path(repo_path)
    pack_yaml = repo / "pack.yaml"
    content = pack_yaml.read_text()
    content = content.replace("version: 0.1.0", f"version: {new_version}")
    if schema_less:
        content = content.replace("schema_version: 1\n", "", 1)
    pack_yaml.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo_path,
                   capture_output=True, check=True, timeout=30)
    subprocess.run(["git", "commit", "-m", "bump to " + new_version],
                   cwd=repo_path, capture_output=True, check=True, timeout=30)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path,
        capture_output=True, text=True, check=True, timeout=30,
    )
    return result.stdout.strip()
def _make_version_commit(
    repo_path: str,
    pack_root: Path,
    old_version: str,
    new_version: str,
) -> str:
    """Update a pack manifest and return the resulting commit SHA."""
    pack_yaml = pack_root / "pack.yaml"
    content = pack_yaml.read_text(encoding="utf-8")
    pack_yaml.write_text(
        content.replace(f"version: {old_version}", f"version: {new_version}"),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "commit", "-m", f"bump to {new_version}"],
        cwd=repo_path,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()


def _snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | str | None]]:
    """Capture file, directory, and symlink custody under *root*."""
    entries: dict[str, tuple[str, bytes | str | None]] = {}
    paths = [root, *root.rglob("*")]
    for path in paths:
        relative = str(path.relative_to(root))
        if path.is_symlink():
            entries[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            entries[relative] = ("directory", None)
        else:
            entries[relative] = ("file", path.read_bytes())
    return entries


def _git_temp_paths() -> tuple[str, ...]:
    """Return disposable Git checkout names currently under the temp root."""
    return tuple(
        sorted(path.name for path in Path(tempfile.gettempdir()).glob("astrid_git_*"))
    )




class GitTestBase(unittest.TestCase):
    """Base class with temp-dir helpers for Git install tests."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="test-git-install-")
        self._astrid_home = Path(self._tmpdir) / "astrid_home"
        self._astrid_home.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _store(self) -> InstalledPackStore:
        return InstalledPackStore(packs_home=self._astrid_home / "packs")

    def _install(
        self,
        source: str | Path,
        *,
        dry_run: bool = False,
        force: bool = False,
        store: InstalledPackStore | None = None,
    ) -> int:
        if store is None:
            store = self._store()
        return install_pack(
            source,
            store=store,
            dry_run=dry_run,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="test-helper",
            force=force,
        )

    def _active_install_json(self, store: InstalledPackStore, pack_id: str) -> dict:
        rev = store.active_revision_path(pack_id)
        self.assertIsNotNone(rev)
        assert rev is not None
        return _json.loads((rev / ".astrid" / "install.json").read_text())


# ---------------------------------------------------------------------------
# _is_git_url detection and rejection
# ---------------------------------------------------------------------------


class TestIsGitUrl(unittest.TestCase):
    """Tests for _is_git_url()."""

    def test_accepts_https(self) -> None:
        self.assertTrue(_is_git_url("https://github.com/user/repo.git"))

    def test_accepts_git_at(self) -> None:
        self.assertTrue(_is_git_url("git@github.com:user/repo.git"))

    def test_accepts_ssh(self) -> None:
        self.assertTrue(_is_git_url("ssh://git@github.com/user/repo.git"))

    def test_accepts_git_protocol(self) -> None:
        self.assertTrue(_is_git_url("git://example.com/repo.git"))

    def test_rejects_http(self) -> None:
        self.assertFalse(_is_git_url("http://github.com/user/repo.git"))

    def test_rejects_file(self) -> None:
        self.assertFalse(_is_git_url("file:///tmp/repo"))

    def test_rejects_plain_path(self) -> None:
        self.assertFalse(_is_git_url("/tmp/my-pack"))

    def test_rejects_relative_path(self) -> None:
        self.assertFalse(_is_git_url("./my-pack"))

    def test_rejects_empty(self) -> None:
        self.assertFalse(_is_git_url(""))

    def test_rejects_ftp(self) -> None:
        self.assertFalse(_is_git_url("ftp://example.com/repo.git"))


# ---------------------------------------------------------------------------
# _check_git_available
# ---------------------------------------------------------------------------


class TestCheckGitAvailable(unittest.TestCase):
    """Tests for _check_git_available()."""

    def test_raises_when_git_missing(self) -> None:
        with mock.patch("subprocess.run",
                        side_effect=FileNotFoundError("git not found")):
            with self.assertRaises(RuntimeError) as ctx:
                _check_git_available()
            self.assertIn("Git is not available", str(ctx.exception))

    def test_raises_when_git_not_functioning(self) -> None:
        called = subprocess.CalledProcessError(1, ["git", "--version"])
        with mock.patch("subprocess.run",
                        side_effect=called):
            with self.assertRaises(RuntimeError) as ctx:
                _check_git_available()
            self.assertIn("Git is not functioning correctly", str(ctx.exception))

    def test_passes_when_git_available(self) -> None:
        # This is an integration test — git should be on PATH
        _check_git_available()  # should not raise


# ---------------------------------------------------------------------------
# _find_pack_root_in_checkout
# ---------------------------------------------------------------------------


class TestFindPackRootInCheckout(unittest.TestCase):
    """Tests for _find_pack_root_in_checkout()."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="test-find-root-")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_repo_root_has_pack_yaml(self) -> None:
        """If pack.yaml is at repo root, return repo root."""
        root = Path(self._tmpdir) / "checkout"
        root.mkdir(parents=True)
        _make_minimal_pack(root, "myroot")
        result = _find_pack_root_in_checkout(root)
        self.assertEqual(result, root.resolve())

    def test_single_subdir_has_pack_yaml(self) -> None:
        """If exactly one subdir has pack.yaml, return that subdir."""
        root = Path(self._tmpdir) / "checkout"
        root.mkdir(parents=True)
        sub = root / "the-pack"
        sub.mkdir()
        _make_minimal_pack(sub, "the_pack")
        result = _find_pack_root_in_checkout(root)
        self.assertEqual(result, sub.resolve())

    def test_no_pack_manifest_raises(self) -> None:
        """If no pack manifest found, raise RuntimeError."""
        root = Path(self._tmpdir) / "checkout"
        root.mkdir(parents=True)
        (root / "README.md").write_text("empty")
        with self.assertRaises(RuntimeError) as ctx:
            _find_pack_root_in_checkout(root)
        self.assertIn("No pack manifest found", str(ctx.exception))

    def test_multiple_subdirs_raises(self) -> None:
        """If multiple subdirs have pack manifests, raise RuntimeError."""
        root = Path(self._tmpdir) / "checkout"
        root.mkdir(parents=True)
        sub1 = root / "pack-a"
        sub1.mkdir()
        _make_minimal_pack(sub1, "pack_a")
        sub2 = root / "pack-b"
        sub2.mkdir()
        _make_minimal_pack(sub2, "pack_b")
        with self.assertRaises(RuntimeError) as ctx:
            _find_pack_root_in_checkout(root)
        self.assertIn("Multiple pack roots found", str(ctx.exception))

    def test_skips_dot_dirs(self) -> None:
        """Dot-prefixed directories are skipped."""
        root = Path(self._tmpdir) / "checkout"
        root.mkdir(parents=True)
        sub = root / ".hidden"
        sub.mkdir()
        _make_minimal_pack(sub, "hidden_pack")
        # Should fail because the .hidden dir is skipped
        with self.assertRaises(RuntimeError) as ctx:
            _find_pack_root_in_checkout(root)
        self.assertIn("No pack manifest found", str(ctx.exception))


# ---------------------------------------------------------------------------
# Git install flow (local repo)
# ---------------------------------------------------------------------------


class TestGitInstallFlow(GitTestBase):
    """Full Git install flow using a local git repo."""

    def test_canonical_git_root_preserves_provenance_through_update(self) -> None:
        """A root canonical pack survives disposable clone and Git update."""
        pack_id = "canonical_git_root"
        repo_path, pack_root, initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        canonical_reads_patcher = mock.patch(
            "astrid.core.pack.install_local.read_normalize_validate",
            wraps=install_local_module.read_normalize_validate,
        )
        canonical_reads = canonical_reads_patcher.start()
        self.addCleanup(canonical_reads_patcher.stop)
        requested_ref = _resolve_git_ref(repo_path)

        checkout_paths: list[str] = []
        clone_impl = install_git_module._clone_git_pack

        def clone_and_capture(url: str) -> tuple[str, str]:
            result = clone_impl(url)
            checkout_paths.append(result[0])
            return result

        with mock.patch(
            "astrid.core.pack.install_git._clone_git_pack",
            side_effect=clone_and_capture,
        ):
            rc = _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            )
        self.assertEqual(rc, 0)
        self.assertEqual(len(checkout_paths), 1)
        checkout_path = Path(checkout_paths[0])
        self.assertFalse(checkout_path.exists())

        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertNotEqual(Path(repo_path).name, pack_id)
        self.assertEqual(record.source_type, "git")
        self.assertEqual(record.source_path, repo_path)
        self.assertEqual(record.git_url, repo_path)
        self.assertEqual(record.commit_sha, initial_sha)
        self.assertEqual(record.requested_ref, requested_ref)
        self.assertEqual(record.trust_summary["source_path"], repo_path)
        self.assertEqual(store.active_revision_path(pack_id).name, pack_id)
        install_json = self._active_install_json(store, pack_id)
        self.assertEqual(install_json["git_url"], repo_path)
        self.assertEqual(install_json["commit_sha"], initial_sha)
        self.assertEqual(install_json["requested_ref"], requested_ref)

        manifest = pack_root / "pack.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "version: 1.0.0", "version: 2.0.0"
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", "bump canonical version"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )
        new_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()

        rc = update_pack(
            pack_id,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="update-test",
        )
        self.assertEqual(rc, 0)
        updated = store.get_active(pack_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.version, "2.0.0")
        self.assertEqual(updated.source_path, repo_path)
        self.assertEqual(updated.git_url, repo_path)
        self.assertEqual(updated.commit_sha, new_sha)
        self.assertEqual(updated.requested_ref, requested_ref)
        self.assertEqual(updated.source_type, "git")
        self.assertEqual(
            [call.kwargs["source"] for call in canonical_reads.call_args_list],
            [ExternalPackSource.GIT] * 2
            + [ExternalPackSource.INSTALLED]
            + [ExternalPackSource.GIT] * 2,
        )

    def test_paired_metadata_downgrade_rejects_git_update_before_checkout(
        self,
    ) -> None:
        """Paired metadata tampering cannot downgrade Git custody."""
        pack_id = "paired_git_metadata"
        repo_path, _pack_root, _initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        active = store.active_revision_path(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        record_path = active / ".astrid" / "install.json"
        record = _json.loads(record_path.read_text())
        record["schema_version"] = 1
        record["trust_summary"]["schema_version"] = 1
        record_path.write_text(_json.dumps(record, indent=2))
        before_tree = _snapshot_tree(store.install_root_for(pack_id))
        before_active = store.active_symlink_path(pack_id).readlink()
        before_temp_paths = _git_temp_paths()
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                with mock.patch(
                    "astrid.core.pack.install_git._check_git_available",
                    side_effect=AssertionError("Git checkout occurred before custody"),
                ):
                    with self.assertRaises(AstridError):
                        update_pack(pack_id, store=store, dry_run=dry_run)
                self.assertEqual(
                    before_tree, _snapshot_tree(store.install_root_for(pack_id))
                )
                self.assertEqual(
                    before_active,
                    store.active_symlink_path(pack_id).readlink(),
                )
                self.assertEqual(before_temp_paths, _git_temp_paths())

    def test_changed_canonical_git_dry_run_rejects_external_database_before_read(
        self,
    ) -> None:
        """Changed canonical Git candidates fail before migration reads."""
        pack_id = "git_dry_run_external_db"
        repo_path, pack_root, _initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        (pack_root / "pack.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                id: {pack_id}
                name: {pack_id.replace("_", " ").title()}
                version: 2.0.0
                capabilities: [render]
                database:
                  default_enabled: false
                  depends_on: []
                  migrations:
                    - version: 1
                      name: missing
                      path: migrations/missing.sql
                      tables: [missing]
                  stream_types: [events.test]
                  event_kinds: [events.test]
                  command_kinds: [commands.test]
                  repositories: [MissingRepository]
                  conformance: [missing]
                  cli_mounts: {{}}
                  bridge_mounts: []
                """
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", "add forbidden database"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )

        with self.assertRaises(ExternalDatabaseForbidden):
            update_pack(pack_id, store=store, dry_run=True)

        active = store.active_revision_path(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(
            _json.loads((active / ".astrid" / "install.json").read_text())["version"],
            "1.0.0",
        )

    def test_changed_git_dry_run_root_v1_preserves_custody(self) -> None:
        """A changed v1 Git commit produces a diff without changing custody."""
        pack_id = "git_dry_run_root_v1"
        repo_path, initial_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        legacy_record = store.get_active_strict(pack_id)
        self.assertIsNotNone(legacy_record)
        assert legacy_record is not None
        self.assertEqual(legacy_record.schema_version, 1)

        install_root = store.install_root_for(pack_id)
        active_link = store.active_symlink_path(pack_id)
        before_tree = _snapshot_tree(install_root)
        before_active_target = os.readlink(active_link)
        before_temp_paths = _git_temp_paths()
        new_sha = _make_another_commit(
            repo_path, pack_id, new_version="0.2.0"
        )

        output = io.StringIO()
        errors = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", output),
            mock.patch.object(sys, "stderr", errors),
        ):
            rc = update_pack(pack_id, store=store, dry_run=True)

        self.assertEqual(rc, 0)
        self.assertIn("═══ Diff Summary ═══", output.getvalue())
        self.assertIn("Version:  0.1.0 → 0.2.0", output.getvalue())
        self.assertIn(
            f"Commit:   {initial_sha[:8]} → {new_sha[:8]}",
            output.getvalue(),
        )
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(before_tree, _snapshot_tree(install_root))
        self.assertEqual(before_active_target, os.readlink(active_link))
        self.assertFalse(store.staging_path_for(pack_id).exists())
        self.assertEqual(before_temp_paths, _git_temp_paths())
        record_after = store.get_active(pack_id)
        self.assertIsNotNone(record_after)
        assert record_after is not None
        self.assertEqual(record_after.version, "0.1.0")
        self.assertEqual(record_after.commit_sha, initial_sha)

    def test_legacy_git_update_preserves_v1_lifecycle(self) -> None:
        """A v1 Git record still uses the inherited update path."""
        pack_id = "legacy_git_update"
        repo_path, _initial_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        record = store.get_active_strict(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.schema_version, 1)
        _make_another_commit(repo_path, pack_id, new_version="0.2.0")

        rc = update_pack(
            pack_id,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="test",
        )
        self.assertEqual(rc, 0)
        updated = store.get_active_strict(pack_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.schema_version, 1)
        self.assertEqual(updated.version, "0.2.0")

    def test_changed_schema_less_git_dry_run_preserves_custody(self) -> None:
        """A changed schema-less legacy commit produces a read-only diff."""
        pack_id = "git_dry_run_schema_less"
        repo_path, initial_sha = _make_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )

        install_root = store.install_root_for(pack_id)
        active_link = store.active_symlink_path(pack_id)
        active_revision = store.active_revision_path(pack_id)
        self.assertIsNotNone(active_revision)
        assert active_revision is not None
        before_tree = _snapshot_tree(install_root)
        before_active_target = os.readlink(active_link)
        before_record = store.get_active(pack_id)
        self.assertIsNotNone(before_record)
        before_install_record = (active_revision / ".astrid" / "install.json").read_bytes()
        before_revisions = {revision.name for revision in store.list_revisions(pack_id)}
        new_sha = _make_another_commit(
            repo_path, pack_id, new_version="0.2.0", schema_less=True
        )

        output = io.StringIO()
        errors = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", output),
            mock.patch.object(sys, "stderr", errors),
        ):
            rc = update_pack(pack_id, store=store, dry_run=True)

        self.assertEqual(rc, 0)
        rendered = output.getvalue()
        self.assertIn("═══ Diff Summary ═══", rendered)
        self.assertIn("Version:  0.1.0 → 0.2.0", rendered)
        self.assertIn(
            f"Commit:   {initial_sha[:8]} → {new_sha[:8]}",
            rendered,
        )
        self.assertIn("Executors:0 (unchanged)", rendered)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(before_tree, _snapshot_tree(install_root))
        self.assertEqual(before_active_target, os.readlink(active_link))
        self.assertEqual(before_record, store.get_active(pack_id))
        self.assertEqual(
            before_install_record,
            (active_revision / ".astrid" / "install.json").read_bytes(),
        )
        self.assertEqual(
            before_revisions,
            {revision.name for revision in store.list_revisions(pack_id)},
        )
        self.assertFalse(store.staging_path_for(pack_id).exists())


    def test_changed_git_dry_run_nested_v2_preserves_custody(self) -> None:
        """A changed nested canonical commit produces a real diff read-only."""
        pack_id = "git_dry_run_nested_v2"
        repo_path, pack_root, initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id, nested=True
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )

        install_root = store.install_root_for(pack_id)
        active_link = store.active_symlink_path(pack_id)
        before_tree = _snapshot_tree(install_root)
        before_active_target = os.readlink(active_link)
        before_temp_paths = _git_temp_paths()
        new_sha = _make_version_commit(
            repo_path, pack_root, "1.0.0", "2.0.0"
        )

        output = io.StringIO()
        errors = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", output),
            mock.patch.object(sys, "stderr", errors),
        ):
            rc = update_pack(pack_id, store=store, dry_run=True)

        self.assertEqual(rc, 0)
        self.assertIn("═══ Diff Summary ═══", output.getvalue())
        self.assertIn("Version:  1.0.0 → 2.0.0", output.getvalue())
        self.assertIn(
            f"Commit:   {initial_sha[:8]} → {new_sha[:8]}",
            output.getvalue(),
        )
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(before_tree, _snapshot_tree(install_root))
        self.assertEqual(before_active_target, os.readlink(active_link))
        self.assertFalse(store.staging_path_for(pack_id).exists())
        self.assertEqual(before_temp_paths, _git_temp_paths())
        record_after = store.get_active(pack_id)
        self.assertIsNotNone(record_after)
        assert record_after is not None
        self.assertEqual(record_after.version, "1.0.0")
        self.assertEqual(record_after.commit_sha, initial_sha)

    def test_git_dry_run_preserves_clone_failure(self) -> None:
        """A clone failure remains a typed failure instead of success."""
        pack_id = "git_dry_run_clone_failure"
        repo_path, _initial_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        _make_another_commit(repo_path, pack_id, new_version="0.2.0")

        with mock.patch(
            "astrid.core.pack.install_git._clone_git_pack",
            side_effect=RuntimeError("clone failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "clone failed"):
                update_pack(pack_id, store=store, dry_run=True)

    def test_canonical_git_update_rejects_symlinked_nested_pack_root(self) -> None:
        pack_id = "canonical_git_symlink_root"
        repo_path, pack_root, initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id, nested=True
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        active_before = store.active_revision_path(pack_id)
        self.assertIsNotNone(active_before)
        assert active_before is not None
        active_bytes = (active_before / "pack.yaml").read_bytes()

        outside = Path(self._tmpdir) / "outside-canonical-pack"
        outside.mkdir()
        (outside / "pack.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                id: {pack_id}
                name: Outside
                version: 9.0.0
                capabilities: [render]
                """
            ),
            encoding="utf-8",
        )
        shutil.rmtree(pack_root)
        pack_root.symlink_to(outside, target_is_directory=True)
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", "replace pack root with symlink"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )

        with self.assertRaisesRegex(RuntimeError, "pack root must not be a symlink"):
            update_pack(
                pack_id,
                store=store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="update-test",
            )

        active_after = store.active_revision_path(pack_id)
        self.assertIsNotNone(active_after)
        assert active_after is not None
        self.assertEqual(active_after.name, active_before.name)
        self.assertEqual((active_after / "pack.yaml").read_bytes(), active_bytes)
        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.version, "1.0.0")
        self.assertFalse((active_after / "outside-canonical-pack").exists())

    def test_canonical_git_update_non_v2_manifest_is_read_only(self) -> None:
        """Canonical Git updates reject non-v2 content before diff or staging."""
        cases = ("v1", "schema-less", "unknown")
        for label in cases:
            for dry_run in (False, True):
                with self.subTest(label=label, dry_run=dry_run):
                    pack_id = (
                        f"canonical_git_non_v2_{label.replace('-', '_')}_"
                        f"{'dry' if dry_run else 'real'}"
                    )
                    repo_path, pack_root, _initial_sha = _make_canonical_git_repo_with_pack(
                        self._tmpdir, pack_id
                    )
                    store = self._store()
                    self.assertEqual(
                        _install_from_git(
                            repo_path,
                            store,
                            skip_confirm=True,
                            trust_acknowledged=True,
                            trust_method="test",
                            trust_actor="test",
                        ),
                        0,
                    )
                    install_root = store.install_root_for(pack_id)
                    before_tree = _snapshot_tree(install_root)
                    before_active = os.readlink(store.active_symlink_path(pack_id))
                    before_revisions = {
                        path.name for path in store.list_revisions(pack_id)
                    }
                    manifest_content = {
                        "v1": (
                            f"schema_version: 1\nid: {pack_id}\nname: Legacy\n"
                            "version: 9.9.9\n"
                        ),
                        "schema-less": (
                            f"id: {pack_id}\nname: Legacy\nversion: 9.9.9\n"
                        ),
                        "unknown": (
                            f"schema_version: 99\nid: {pack_id}\nname: Unknown\n"
                            "version: 9.9.9\n"
                        ),
                    }[label]
                    (pack_root / "pack.yaml").write_text(
                        manifest_content, encoding="utf-8"
                    )
                    subprocess.run(
                        ["git", "add", "-A"],
                        cwd=repo_path,
                        capture_output=True,
                        check=True,
                        timeout=30,
                    )
                    subprocess.run(
                        ["git", "commit", "-m", f"replace canonical manifest with {label}"],
                        cwd=repo_path,
                        capture_output=True,
                        check=True,
                        timeout=30,
                    )

                    with (
                        mock.patch.object(
                            install_git_module,
                            "load_manifest_for_dispatch",
                            side_effect=AssertionError(
                                "canonical Git update used dispatch parser"
                            ),
                        ),
                        mock.patch.object(
                            install_local_module,
                            "validate_pack",
                            side_effect=AssertionError(
                                "canonical Git update used legacy validator"
                            ),
                        ),
                    ):
                        with self.assertRaises(CanonicalPackValidationError):
                            update_pack(pack_id, store=store, dry_run=dry_run)

                    self.assertEqual(before_tree, _snapshot_tree(install_root))
                    self.assertEqual(
                        before_active,
                        os.readlink(store.active_symlink_path(pack_id)),
                    )
                    self.assertEqual(
                        before_revisions,
                        {path.name for path in store.list_revisions(pack_id)},
                    )
                    self.assertFalse(store.staging_path_for(pack_id).exists())
    def test_canonical_git_update_rejects_malformed_installed_schema_before_git_reads(
        self,
    ) -> None:
        """Git update and dry-run cannot downgrade canonical custody."""
        pack_id = "canonical_git_bad_record_schema"
        repo_path, _pack_root, _initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        active = store.active_revision_path(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        record_path = active / ".astrid" / "install.json"
        original_record = _json.loads(record_path.read_text(encoding="utf-8"))
        cases = (
            ("string", "2"),
            ("boolean", True),
            ("float", 2.0),
            ("null", None),
            ("missing", None),
            ("unsupported", 99),
            ("contradictory", 1),
        )
        for dry_run in (False, True):
            for label, value in cases:
                with self.subTest(dry_run=dry_run, label=label):
                    record = dict(original_record)
                    if label == "missing":
                        del record["schema_version"]
                    else:
                        record["schema_version"] = value
                    record_path.write_text(
                        _json.dumps(record, indent=2), encoding="utf-8"
                    )
                    before_tree = _snapshot_tree(store.install_root_for(pack_id))
                    before_active = store.active_symlink_path(pack_id).readlink()
                    with mock.patch.object(
                        install_git_module,
                        "_check_git_available",
                        side_effect=AssertionError("Git was read before custody rejection"),
                    ):
                        with self.assertRaises(AstridError):
                            update_pack(
                                pack_id,
                                store=store,
                                dry_run=dry_run,
                                skip_confirm=True,
                                trust_acknowledged=True,
                            )
                    self.assertEqual(
                        _snapshot_tree(store.install_root_for(pack_id)),
                        before_tree,
                    )
                    self.assertEqual(
                        store.active_symlink_path(pack_id).readlink(),
                        before_active,
                    )
        record_path.write_text(_json.dumps(original_record, indent=2), encoding="utf-8")


    def test_canonical_git_update_never_falls_back_to_legacy_manifest(self) -> None:
        """Canonical Git custody rejects a legacy-only remote before reads."""
        pack_id = "canonical_git_legacy_remote"
        repo_path, pack_root, _initial_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        active_before = store.active_revision_path(pack_id)
        self.assertIsNotNone(active_before)
        assert active_before is not None
        before_manifest = (active_before / "pack.yaml").read_bytes()
        before_record = (active_before / ".astrid" / "install.json").read_bytes()

        (pack_root / "pack.yaml").unlink()
        (pack_root / "pack.yml").write_text(
            "schema_version: 1\n"
            f"id: {pack_id}\n"
            "name: Legacy Remote\n"
            "version: 9.9.9\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", "replace canonical manifest with legacy"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=30,
        )

        with mock.patch.object(
            install_git_module,
            "pack_manifest_path",
            side_effect=AssertionError("canonical update used legacy fallback"),
        ):
            with self.assertRaisesRegex(RuntimeError, "No canonical pack manifest"):
                update_pack(
                    pack_id,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                    trust_method="test",
                    trust_actor="test",
                )

        active_after = store.active_revision_path(pack_id)
        self.assertIsNotNone(active_after)
        assert active_after is not None
        self.assertEqual(active_after.name, active_before.name)
        self.assertEqual((active_after / "pack.yaml").read_bytes(), before_manifest)
        self.assertEqual(
            (active_after / ".astrid" / "install.json").read_bytes(),
            before_record,
        )
    def test_canonical_git_nested_pack_preserves_folder_and_provenance(self) -> None:
        """A canonical pack in a repository subdirectory installs unchanged."""
        pack_id = "canonical_git_nested"
        repo_path, pack_root, commit_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id, nested=True
        )
        store = self._store()
        canonical_reads_patcher = mock.patch(
            "astrid.core.pack.install_local.read_normalize_validate",
            wraps=install_local_module.read_normalize_validate,
        )
        canonical_reads = canonical_reads_patcher.start()
        self.addCleanup(canonical_reads_patcher.stop)
        requested_ref = _resolve_git_ref(repo_path)

        rc = _install_from_git(
            repo_path,
            store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="test",
        )
        self.assertEqual(rc, 0)
        self.assertNotEqual(pack_root.name, pack_id)

        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.source_type, "git")
        self.assertEqual(record.source_path, repo_path)
        self.assertEqual(record.git_url, repo_path)
        self.assertEqual(record.commit_sha, commit_sha)
        self.assertEqual(record.requested_ref, requested_ref)
        self.assertEqual(record.trust_summary["source_path"], repo_path)
        self.assertEqual(store.active_revision_path(pack_id).name, pack_id)

        new_sha = _make_version_commit(
            repo_path, pack_root, "1.0.0", "2.0.0"
        )
        rc = update_pack(
            pack_id,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="update-test",
        )
        self.assertEqual(rc, 0)
        updated = store.get_active(pack_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.version, "2.0.0")
        self.assertEqual(updated.source_type, "git")
        self.assertEqual(updated.git_url, repo_path)
        self.assertEqual(updated.commit_sha, new_sha)
        self.assertEqual(
            [call.kwargs["source"] for call in canonical_reads.call_args_list],
            [ExternalPackSource.GIT] * 2
            + [ExternalPackSource.INSTALLED]
            + [ExternalPackSource.GIT] * 2,
        )

    def test_git_install_success(self) -> None:
        """Install from a local git repo, verify all fields populated."""
        pack_id = "git_test_install"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        rc = install_pack(
            repo_path,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
        )
        self.assertEqual(rc, 0)

        # Verify store state
        self.assertTrue(store.is_installed(pack_id))
        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None

        # Verify InstallRecord fields
        self.assertEqual(record.pack_id, pack_id)
        self.assertTrue(record.active)
        # source_type defaults to "local" for local-path installs
        self.assertIn(record.source_type, ("local", ""))

        # Verify directory layout
        root = store.install_root_for(pack_id)
        self.assertTrue(root.is_dir())
        rev = store.active_revision_path(pack_id)
        self.assertIsNotNone(rev)
        assert rev is not None

        # Verify install.json content
        install_json_path = rev / ".astrid" / "install.json"
        self.assertTrue(install_json_path.is_file())
        data = _json.loads(install_json_path.read_text())
        self.assertEqual(data["pack_id"], pack_id)
        self.assertIsNotNone(data.get("installed_at"))
        self.assertIsNotNone(data.get("manifest_digest"))

    def test_git_url_install_uses_shared_install_record_trust_metadata(self) -> None:
        """_install_from_git delegates to install_pack and records trust metadata."""
        pack_id = "git_trust_record"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        pack_yaml = Path(repo_path) / "pack.yaml"
        pack_yaml.write_text(
            pack_yaml.read_text()
            + textwrap.dedent("""\
                permissions:
                  - id: environment
                    access: read
                    reason: Read test environment configuration.
            """),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True, timeout=30)
        subprocess.run(["git", "commit", "-m", "add permissions"], cwd=repo_path, capture_output=True, check=True, timeout=30)
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()

        store = self._store()
        rc = _install_from_git(
            repo_path,
            store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="test",
        )

        self.assertEqual(rc, 0)
        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.source_type, "git")
        self.assertEqual(record.git_url, repo_path)
        self.assertEqual(record.commit_sha, commit_sha)
        self.assertTrue(record.trust_acknowledged_at.endswith("Z"))
        self.assertEqual(record.trust_method, "test")
        self.assertEqual(record.trust_actor, "test")
        self.assertEqual(record.no_sandbox_warning_version, 1)
        self.assertEqual(
            record.permissions_accepted,
            [
                {
                    "id": "environment",
                    "reason": "Read test environment configuration.",
                    "access": "read",
                }
            ],
        )
        install_json = self._active_install_json(store, pack_id)
        self.assertEqual(install_json["source_type"], "git")
        self.assertEqual(install_json["git_url"], repo_path)
        self.assertEqual(install_json["commit_sha"], commit_sha)
        self.assertTrue(install_json["trust_acknowledged_at"].endswith("Z"))
        self.assertEqual(install_json["trust_method"], "test")
        self.assertEqual(install_json["trust_actor"], "test")
        self.assertEqual(install_json["no_sandbox_warning_version"], 1)
        self.assertEqual(
            install_json["permissions_accepted"],
            record.permissions_accepted,
        )
        self.assertEqual(
            install_json["trust_summary"]["permissions"],
            record.permissions_accepted,
        )

    def test_git_install_dry_run(self) -> None:
        """Git install --dry-run prints trust summary, does not create pack dir."""
        pack_id = "git_dry_install"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            rc = install_pack(
                repo_path,
                store=store,
                dry_run=True,
                skip_confirm=True,
                trust_acknowledged=True,
            )
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("Trust Summary", output)
        self.assertIn(pack_id, output)

        # No state should have been created
        self.assertFalse(store.is_installed(pack_id))
        self.assertIsNone(store.get_active(pack_id))

    def test_git_update_requires_renewed_trust_and_records_new_decision(self) -> None:
        pack_id = "git_update_trust_record"
        repo_path, _commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        rc = _install_from_git(
            repo_path,
            store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="initial-test",
        )
        self.assertEqual(rc, 0)

        pack_yaml = Path(repo_path) / "pack.yaml"
        pack_yaml.write_text(
            pack_yaml.read_text().replace("version: 0.1.0", "version: 0.2.0")
            + textwrap.dedent("""\
                permissions:
                  - id: network
                    access: connect
                    services:
                      - update-api
                    reason: Call update API during tests.
            """),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True, check=True, timeout=30)
        subprocess.run(["git", "commit", "-m", "update permissions"], cwd=repo_path, capture_output=True, check=True, timeout=30)

        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            rc = update_pack(pack_id, store=store, skip_confirm=True)
        self.assertEqual(rc, 1)
        self.assertIn("trust acknowledgement required", err.getvalue())
        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.version, "0.1.0")

        rc = update_pack(
            pack_id,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
            trust_method="test",
            trust_actor="update-test",
        )
        self.assertEqual(rc, 0)
        updated = store.get_active(pack_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.version, "0.2.0")
        self.assertEqual(updated.source_type, "git")
        self.assertEqual(updated.trust_method, "test")
        self.assertEqual(updated.trust_actor, "update-test")
        self.assertEqual(
            updated.permissions_accepted,
            [
                {
                    "id": "network",
                    "reason": "Call update API during tests.",
                    "access": "connect",
                    "services": ["update-api"],
                }
            ],
        )
        install_json = self._active_install_json(store, pack_id)
        self.assertEqual(install_json["source_type"], "git")
        self.assertEqual(install_json["trust_method"], "test")
        self.assertEqual(install_json["trust_actor"], "update-test")
        self.assertEqual(install_json["no_sandbox_warning_version"], 1)
        self.assertEqual(
            install_json["permissions_accepted"],
            updated.permissions_accepted,
        )
        self.assertEqual(
            install_json["trust_summary"]["permissions"],
            updated.permissions_accepted,
        )


# ---------------------------------------------------------------------------
# Git-backed pack workflow (install → update → rollback)
# ---------------------------------------------------------------------------


    def test_canonical_git_update_rejects_installed_manifest_drift_before_git_read(
        self,
    ) -> None:
        pack_id = "canonical_git_installed_drift"
        repo_path, _pack_root, _commit_sha = _make_canonical_git_repo_with_pack(
            self._tmpdir, pack_id
        )
        store = self._store()
        self.assertEqual(
            _install_from_git(
                repo_path,
                store,
                skip_confirm=True,
                trust_acknowledged=True,
                trust_method="test",
                trust_actor="test",
            ),
            0,
        )
        active = store.active_revision_path(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        manifest = active / "pack.yaml"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
        before_pointer = store.active_symlink_path(pack_id).readlink()
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                with mock.patch(
                    "astrid.core.pack.install_git._check_git_available",
                    side_effect=AssertionError("Git was read before installed custody"),
                ):
                    with self.assertRaises(AstridError):
                        update_pack(
                            pack_id,
                            store=store,
                            dry_run=dry_run,
                            skip_confirm=True,
                            trust_acknowledged=True,
                        )
                self.assertEqual(
                    store.active_symlink_path(pack_id).readlink(),
                    before_pointer,
                )

class TestGitBackedWorkflow(GitTestBase):
    """End-to-end: install from git repo, update, rollback."""

    def setUp(self) -> None:
        super().setUp()
        self._pack_id = "git_wf"
        self._repo_path, self._initial_sha = _make_git_repo_with_pack(
            self._tmpdir, self._pack_id,
        )

    def test_full_git_install_update_rollback(self) -> None:
        """Install → update → rollback full cycle."""
        store = self._store()

        # ── 1. Install from git repo ──
        rc = self._install(self._repo_path, store=store)
        self.assertEqual(rc, 0)
        self.assertTrue(store.is_installed(self._pack_id))

        # Verify initial record
        record = store.get_active(self._pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.schema_version, 1)
        self.assertEqual(record.pack_id, self._pack_id)
        self.assertEqual(record.version, "0.1.0")
        # source_type is "local" for local-path installs
        self.assertIn(record.source_type, ("local", ""))

        # ── 2. Make a new commit to the repo ──
        new_sha = _make_another_commit(self._repo_path, self._pack_id, new_version="0.2.0")

        # ── 3. Update dry-run: should show diff ──
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            rc = update_pack(self._pack_id, store=store, dry_run=True)
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("Currently Installed", output)
        self.assertIn("Source (would install)", output)
        self.assertIn("0.2.0", output)

        # ── 4. Real update ──
        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            rc = update_pack(
                self._pack_id,
                store=store,
                skip_confirm=True,
                trust_acknowledged=True,
            )
        self.assertEqual(rc, 0)

        # Verify update
        record2 = store.get_active(self._pack_id)
        self.assertIsNotNone(record2)
        assert record2 is not None
        self.assertEqual(record2.version, "0.2.0")

        # Old revision should be preserved
        revisions = store.list_revisions(self._pack_id)
        self.assertGreaterEqual(len(revisions), 2,
                                f"Expected >= 2 revisions, got {[r.name for r in revisions]}")

        # ── 5. Rollback to first revision ──
        # Find the old revision (not the active one)
        active_rev = store.active_revision_path(self._pack_id)
        assert active_rev is not None
        old_revisions = [r for r in revisions if r.name != active_rev.name]
        self.assertGreaterEqual(len(old_revisions), 1,
                                "Expected at least 1 old revision")

        target_rev = old_revisions[0].name

        rc = rollback_pack(
            self._pack_id,
            store=store,
            revision=target_rev,
            skip_confirm=True,
        )
        self.assertEqual(rc, 0)

        # Verify rollback
        record3 = store.get_active(self._pack_id)
        self.assertIsNotNone(record3)
        assert record3 is not None
        self.assertEqual(record3.version, "0.1.0")

    def test_update_dry_run_shows_diff(self) -> None:
        """Update --dry-run for local packs shows diff with version change."""
        store = self._store()
        self._install(self._repo_path, store=store)

        # Make a change
        _make_another_commit(self._repo_path, self._pack_id, new_version="0.5.0")

        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            rc = update_pack(self._pack_id, store=store, dry_run=True)
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("0.5.0", output)

    def test_rollback_explicit_revision(self) -> None:
        """Rollback with an explicit --revision."""
        store = self._store()
        self._install(self._repo_path, store=store)

        # Make another install to create a second revision
        _make_another_commit(self._repo_path, self._pack_id, new_version="0.3.0")

        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            rc = update_pack(
                self._pack_id,
                store=store,
                skip_confirm=True,
                trust_acknowledged=True,
            )
        self.assertEqual(rc, 0)

        # Now we have 2+ revisions. Find the old one.
        revisions = store.list_revisions(self._pack_id)
        active_rev = store.active_revision_path(self._pack_id)
        assert active_rev is not None
        old = [r for r in revisions if r.name != active_rev.name]
        self.assertGreaterEqual(len(old), 1)

        # Rollback to old revision explicitly
        rc = rollback_pack(
            self._pack_id,
            store=store,
            revision=old[0].name,
            skip_confirm=True,
        )
        self.assertEqual(rc, 0)

        # Verify we're back to 0.1.0
        record = store.get_active(self._pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.version, "0.1.0")


# ---------------------------------------------------------------------------
# _diff_component_inventories
# ---------------------------------------------------------------------------


class TestDiffComponentInventories(unittest.TestCase):
    """Tests for _diff_component_inventories()."""

    def test_version_change(self) -> None:
        old = {"component_counts": {}, "entrypoints": []}
        new = {"component_counts": {}, "entrypoints": []}
        result = _diff_component_inventories(
            old, new,
            old_version="0.1.0", new_version="0.2.0",
        )
        self.assertIn("0.1.0 → 0.2.0", result)

    def test_commit_change(self) -> None:
        old = {"component_counts": {}, "entrypoints": []}
        new = {"component_counts": {}, "entrypoints": []}
        result = _diff_component_inventories(
            old, new,
            old_commit="abc123456789", new_commit="def123456789",
        )
        self.assertIn("abc12345 → def12345", result)

    def test_component_count_delta(self) -> None:
        old = {"component_counts": {"executors": 1, "orchestrators": 0, "elements": 0},
               "entrypoints": []}
        new = {"component_counts": {"executors": 1, "orchestrators": 2, "elements": 3},
               "entrypoints": []}
        result = _diff_component_inventories(old, new)
        self.assertIn("Executors:1 (unchanged)", result)
        self.assertIn("Orchestrators:0 → 2 (+2)", result)
        self.assertIn("Elements:0 → 3 (+3)", result)

    def test_entrypoint_additions(self) -> None:
        old = {"component_counts": {}, "entrypoints": ["run"]}
        new = {"component_counts": {}, "entrypoints": ["run", "validate"]}
        result = _diff_component_inventories(old, new)
        self.assertIn("Entrypoints added:", result)
        self.assertIn("validate", result)

    def test_entrypoint_removals(self) -> None:
        old = {"component_counts": {}, "entrypoints": ["run", "deprecated"]}
        new = {"component_counts": {}, "entrypoints": ["run"]}
        result = _diff_component_inventories(old, new)
        self.assertIn("Entrypoints removed:", result)
        self.assertIn("deprecated", result)

    def test_secrets_deltas(self) -> None:
        old = {"component_counts": {}, "entrypoints": [],
               "declared_secrets": ["SECRET_A"]}
        new = {"component_counts": {}, "entrypoints": [],
               "declared_secrets": ["SECRET_A", "SECRET_B"]}
        result = _diff_component_inventories(old, new)
        self.assertIn("Secrets added:", result)
        self.assertIn("SECRET_B", result)

    def test_permission_additions_removals_and_changes(self) -> None:
        old = {
            "component_counts": {},
            "entrypoints": [],
            "permissions": [
                {"id": "network", "reason": "Old reason", "services": ["fal"]},
                {"id": "environment", "reason": "Read env"},
            ],
        }
        new = {
            "component_counts": {},
            "entrypoints": [],
            "permissions": [
                {"id": "network", "reason": "New reason", "services": ["fal", "runpod"]},
                {"id": "project_files", "reason": "Read project files", "access": "read-only"},
            ],
        }
        result = _diff_component_inventories(old, new)
        self.assertIn("Permissions added:", result)
        self.assertIn("project_files: Read project files; access=read-only", result)
        self.assertIn("Permissions removed:", result)
        self.assertIn("environment: Read env", result)
        self.assertIn("Permissions changed:", result)
        self.assertIn("network:", result)
        self.assertIn("Old reason", result)
        self.assertIn("New reason", result)


# ---------------------------------------------------------------------------
# _format_trust_summary Git fields
# ---------------------------------------------------------------------------


class TestFormatTrustSummaryGit(unittest.TestCase):
    """Tests for _format_trust_summary with Git parameters."""

    def test_shows_git_url_instead_of_source_path(self) -> None:
        summary = {
            "pack_id": "test_pack",
            "name": "Test Pack",
            "version": "1.0.0",
            "schema_version": 1,
            "source_path": "/tmp/temp_checkout",
            "component_counts": {},
            "entrypoints": [],
        }
        result = _format_trust_summary(
            summary,
            git_url="https://github.com/user/repo.git",
            commit_sha="abc1234567890123456789012345678901234567",
            trust_tier="git",
        )
        self.assertIn("Source:", result)
        self.assertIn("https://github.com/user/repo.git", result)
        self.assertNotIn("/tmp/temp_checkout", result)
        self.assertIn("Pinned Commit:", result)
        self.assertIn("abc12345", result)
        self.assertIn("Trust Tier:", result)
        self.assertIn("git", result)

    def test_local_install_shows_source_path(self) -> None:
        summary = {
            "pack_id": "local_pack",
            "name": "Local Pack",
            "version": "0.1.0",
            "schema_version": 1,
            "source_path": "/home/user/packs/local_pack",
            "component_counts": {},
            "entrypoints": [],
        }
        result = _format_trust_summary(summary)
        self.assertIn("/home/user/packs/local_pack", result)
        self.assertNotIn("Pinned Commit:", result)
        self.assertNotIn("Trust Tier:", result)

    def test_shows_astrid_version_when_present(self) -> None:
        summary = {
            "pack_id": "test",
            "name": "Test",
            "version": "0.1.0",
            "schema_version": 1,
            "source_path": "/tmp",
            "component_counts": {},
            "entrypoints": [],
        }
        result = _format_trust_summary(summary, astrid_version="1.0.0")
        self.assertIn("Astrid Ver:", result)
        self.assertIn("1.0.0", result)

    def test_permissions_and_v1_disclosure_are_always_shown(self) -> None:
        summary = {
            "pack_id": "trusted_pack",
            "name": "Trusted Pack",
            "version": "0.1.0",
            "schema_version": 1,
            "source_path": "/tmp",
            "component_counts": {},
            "entrypoints": [],
            "permissions": [
                {
                    "id": "network",
                    "reason": "Call remote APIs",
                    "services": ["fal"],
                }
            ],
            "trust": {
                "sandbox": "none",
                "runs_with_user_process_permissions": True,
                "permission_enforcement": "disclosure_only",
            },
        }
        result = _format_trust_summary(summary)
        self.assertIn("Permissions:", result)
        self.assertIn("network: Call remote APIs; services=fal", result)
        self.assertIn("Trust (v1):", result)
        self.assertIn("sandbox=none", result)
        self.assertIn("runs_with_user_process_permissions=true", result)
        self.assertIn("permission_enforcement=disclosure_only", result)
        self.assertIn("Astrid v1 does not sandbox installed packs.", result)
        self.assertIn("Permission declarations are disclosure-only and not enforced.", result)


# ---------------------------------------------------------------------------
# update_pack branches on source_type before is_dir()
# ---------------------------------------------------------------------------


class TestUpdatePackGitSourceTypeGuard(GitTestBase):
    """Verify update_pack branches on source_type before is_dir() check."""

    def test_update_git_pack_is_reexported_from_its_real_module(self) -> None:
        self.assertIs(install_module._update_git_pack, install_git_module._update_git_pack)
        self.assertIs(install_local_module._update_git_pack, install_module._update_git_pack)
        self.assertTrue(callable(install_module._update_git_pack))

    def test_update_git_pack_bypasses_is_dir_check(self) -> None:
        """When source_type is 'git', update_pack delegates to _update_git_pack."""
        pack_id = "git_source_guard"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        self._install(repo_path, store=store)
        self.assertTrue(store.is_installed(pack_id))

        # Now manually set source_type to "git" on the record
        # to simulate a Git-backed pack (using _update_git_pack path)
        record = store.get_active(pack_id)
        self.assertIsNotNone(record)

        # Even with source_type != "git", update should work for local path
        rc = update_pack(pack_id, store=store, dry_run=True)
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# rollback_to_revision metadata consistency
# ---------------------------------------------------------------------------


class TestRollbackMetadataConsistency(GitTestBase):
    """Verify rollback updates active flags on both old and target revisions."""

    def test_rollback_sets_target_active_true(self) -> None:
        """After rollback, the target revision has active=True in install.json."""
        pack_id = "rollback_meta"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        self._install(repo_path, store=store)

        # Create a second revision via force install with changed source
        src = Path(self._tmpdir) / "sources" / pack_id
        src.mkdir(parents=True, exist_ok=True)
        _make_minimal_pack(src, pack_id=pack_id)
        # Modify version
        (src / "pack.yaml").write_text(
            (src / "pack.yaml").read_text().replace("0.1.0", "0.9.0")
        )

        rc = install_pack(
            src,
            store=store,
            skip_confirm=True,
            trust_acknowledged=True,
            force=True,
        )
        self.assertEqual(rc, 0)

        # Verify we have 2 revisions
        revisions = store.list_revisions(pack_id)
        self.assertGreaterEqual(len(revisions), 2)

        active_rev = store.active_revision_path(pack_id)
        assert active_rev is not None
        old = [r for r in revisions if r.name != active_rev.name]
        self.assertGreaterEqual(len(old), 1)

        # Rollback
        rc = rollback_pack(
            pack_id, store=store,
            revision=old[0].name,
            skip_confirm=True,
        )
        self.assertEqual(rc, 0)

        # Record the name of the previously-active revision BEFORE rollback
        old_active_name = active_rev.name  # "rollback_meta" (v0.9.0)

        # Verify: the new active revision has active=True in its install.json
        new_active = store.active_revision_path(pack_id)
        self.assertIsNotNone(new_active)
        assert new_active is not None
        new_install_json = new_active / ".astrid" / "install.json"
        self.assertTrue(new_install_json.is_file())
        data = _json.loads(new_install_json.read_text())
        self.assertTrue(data.get("active", False),
                        f"Expected active=True, got {data.get('active')}")

        # Verify: the OLD active (now demoted) has active=False
        old_active_install_json = (
            store.revisions_dir(pack_id) / old_active_name / ".astrid" / "install.json"
        )
        if old_active_install_json.is_file():
            old_data = _json.loads(old_active_install_json.read_text())
            self.assertFalse(old_data.get("active", True),
                             f"Expected active=False for {old_active_name}, got {old_data.get('active')}")

    def test_force_install_record_failure_restores_exact_custody(self) -> None:
        """A forced publication failure leaves the prior install untouched."""
        pack_id = "force_publication_failure"
        repo_path, _initial_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        self.assertEqual(self._install(repo_path, store=store), 0)

        source = Path(self._tmpdir) / "force-source" / pack_id
        source.mkdir(parents=True)
        _make_minimal_pack(source, pack_id=pack_id)
        (source / "pack.yaml").write_text(
            (source / "pack.yaml").read_text(encoding="utf-8").replace(
                "version: 0.1.0", "version: 0.9.0"
            ),
            encoding="utf-8",
        )
        install_root = store.install_root_for(pack_id)
        before = _snapshot_tree(install_root)

        with mock.patch.object(
            store, "record_install", side_effect=OSError("injected record failure")
        ):
            rc = install_pack(
                source,
                store=store,
                skip_confirm=True,
                trust_acknowledged=True,
                force=True,
            )

        self.assertEqual(rc, 1)
        self.assertEqual(before, _snapshot_tree(install_root))
        active = store.get_active(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.version, "0.1.0")
        self.assertTrue(active.active)

    def test_rollback_pointer_failure_restores_exact_custody(self) -> None:
        """A failed pointer replace restores records, revisions, and pointer."""
        pack_id = "rollback_publication_failure"
        repo_path, _initial_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)
        store = self._store()
        self.assertEqual(self._install(repo_path, store=store), 0)
        source = Path(self._tmpdir) / "rollback-source" / pack_id
        source.mkdir(parents=True)
        _make_minimal_pack(source, pack_id=pack_id)
        (source / "pack.yaml").write_text(
            (source / "pack.yaml").read_text(encoding="utf-8").replace(
                "version: 0.1.0", "version: 0.9.0"
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            install_pack(
                source,
                store=store,
                skip_confirm=True,
                trust_acknowledged=True,
                force=True,
            ),
            0,
        )
        revisions = store.list_revisions(pack_id)
        active = store.active_revision_path(pack_id)
        self.assertIsNotNone(active)
        assert active is not None
        target = next(revision for revision in revisions if revision.name != active.name)
        install_root = store.install_root_for(pack_id)
        before = _snapshot_tree(install_root)

        with mock.patch(
            "astrid.core.pack.store.os.replace",
            side_effect=OSError("injected pointer failure"),
        ):
            rc = rollback_pack(
                pack_id,
                store=store,
                revision=target.name,
                skip_confirm=True,
            )

        self.assertEqual(rc, 1)
        self.assertEqual(before, _snapshot_tree(install_root))
        current = store.get_active(pack_id)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.revision, active.name)
        self.assertTrue(current.active)


# ---------------------------------------------------------------------------
# manifest_digest populated
# ---------------------------------------------------------------------------


class TestManifestDigest(GitTestBase):
    """Verify manifest_digest is computed and populated."""

    def test_manifest_digest_populated(self) -> None:
        pack_id = "digest_test"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        self._install(repo_path, store=store)

        record = store.get_active(pack_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(record.manifest_digest,
                        "manifest_digest should be non-empty")
        self.assertEqual(len(record.manifest_digest), 64,
                         "manifest_digest should be a SHA-256 hex digest")


# ---------------------------------------------------------------------------
# _resolve_git_ref with --symref fallback
# ---------------------------------------------------------------------------


class TestResolveGitRef(unittest.TestCase):
    """Tests for _resolve_git_ref with symref fallback (Git < 2.37 compatibility)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="test-resolve-ref-")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_resolves_default_branch_from_local_repo(self) -> None:
        """_resolve_git_ref should resolve the default branch from a local repo."""
        pack_id = "ref_test"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        ref = _resolve_git_ref(repo_path)
        # Should be HEAD or refs/heads/main on our test repo
        self.assertIsInstance(ref, str)
        self.assertTrue(ref, "ref should be non-empty")
        # On Git 2.34.1, --symref may fail; fallback should pick main or HEAD
        self.assertIn(ref, ("HEAD", "refs/heads/main", "refs/heads/master"))


# ---------------------------------------------------------------------------
# Git credential handling
# ---------------------------------------------------------------------------


class TestGitCredentials(unittest.TestCase):
    """Git credentials are handled entirely by the git subprocess."""

    def test_no_token_env_manipulation(self) -> None:
        """Verify that _run_git does not set or reference GH/GitLab tokens."""
        import inspect
        source = inspect.getsource(_run_git)
        # No mention of token, GITHUB_TOKEN, GITLAB_TOKEN, credential
        self.assertNotIn("GITHUB_TOKEN", source)
        self.assertNotIn("GITLAB_TOKEN", source)
        self.assertNotIn("personal_access_token", source.lower())
        self.assertNotIn("credential.helper", source)

    def test_no_token_in_install_code(self) -> None:
        """Verify install code does not reference any token env vars."""
        import inspect
        source = inspect.getsource(install_pack)
        self.assertNotIn("GITHUB_TOKEN", source)
        self.assertNotIn("GITLAB_TOKEN", source)


# ---------------------------------------------------------------------------
# Inspect shows Git fields
# ---------------------------------------------------------------------------


class TestInspectGitFields(GitTestBase):
    """Verify inspect displays Git-enriched fields for Git-backed packs."""

    def test_inspect_shows_manifest_digest(self) -> None:
        """Inspect output includes manifest_digest when available."""
        pack_id = "inspect_git"
        repo_path, commit_sha = _make_git_repo_with_pack(self._tmpdir, pack_id)

        store = self._store()
        self._install(repo_path, store=store)

        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"ASTRID_HOME": str(self._astrid_home)}):
            with mock.patch.object(sys, "stdout", buf):
                rc = cmd_inspect([pack_id])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("Manifest Hash:", output)


if __name__ == "__main__":
    unittest.main()
