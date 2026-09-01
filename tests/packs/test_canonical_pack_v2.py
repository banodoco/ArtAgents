from __future__ import annotations

import contextlib
import io
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from astrid.core.pack import PackValidationError, load_pack_manifest
from astrid.core.pack.canonical import (
    BundledCatalog,
    CanonicalPackEntry,
    CanonicalPackValidationError,
    ExternalDatabaseForbidden,
    ExternalPackSource,
    read_normalize_validate,
    validate_canonical_pack,
)
from astrid.core.pack.discovery import (
    ASTRID_PACKS_PATH_ENV,
    discover_canonical_pack_metadata,
    discover_canonical_packs_ordered,
)
from astrid.core.pack.install import (
    install_canonical_pack,
    install_pack,
    rollback_pack,
    update_pack,
)
from astrid.core.pack.store import InstallRecord, InstalledPackStore
from astrid.core.contracts.errors import AstridError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "canonical_pack_v2"

def _copy_fixture_files(source: Path, destination: Path) -> None:
    """Reconstruct a fixture from regular files, not filesystem directories."""
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

def _snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | str | None]]:
    """Capture regular files, directories, and symlink targets."""
    entries: dict[str, tuple[str, bytes | str | None]] = {}
    for path in (root, *root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            entries[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            entries[relative] = ("directory", None)
        else:
            entries[relative] = ("file", path.read_bytes())
    return entries
class CanonicalPackV2Test(unittest.TestCase):


    def test_golden_capability_database_and_combined_entries(self) -> None:
        capability = validate_canonical_pack(FIXTURES / "capability_only")
        database = validate_canonical_pack(FIXTURES / "database_only")
        combined = validate_canonical_pack(FIXTURES / "combined")

        self.assertIsNone(capability.database)
        self.assertEqual(database.database.migration_head, 1)
        self.assertEqual(combined.capability_projection().capabilities, ("references",))
        self.assertEqual(combined.documentation_projection().documentation.kind, "skill")
        self.assertTrue(all(handle.root == combined.root for handle in combined.resources))
        with sqlite3.connect(":memory:") as connection:
            connection.executescript(
                (combined.root / "migrations" / "0001_initial.sql").read_text(encoding="utf-8")
            )
            self.assertIsNotNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                    ("combined_records",),
                ).fetchone()
            )

    def test_golden_forms_replay_from_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_root = Path(tmp)
            entries = {}
            for pack_id in ("capability_only", "database_only", "combined"):
                reconstructed = replay_root / pack_id
                _copy_fixture_files(FIXTURES / pack_id, reconstructed)
                entries[pack_id] = validate_canonical_pack(reconstructed)

        self.assertEqual(set(entries), {"capability_only", "database_only", "combined"})
        self.assertIsNone(entries["capability_only"].database)
        self.assertEqual(entries["database_only"].database.migration_head, 1)
        self.assertEqual(entries["combined"].capability_projection().capabilities, ("references",))



    def test_capability_only_manifest_is_valid_without_other_contributions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "solo"
            root.mkdir()
            (root / "pack.yaml").write_text(
                "schema_version: 2\nid: solo\nname: Solo\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            entry = validate_canonical_pack(root)
            self.assertEqual(entry.capabilities.capabilities, ("render",))
            self.assertEqual(entry.resources, ())

    def test_catalog_is_explicit_root_deterministic_and_projected(self) -> None:
        catalog = BundledCatalog.from_root(FIXTURES)
        self.assertEqual(
            tuple(entry.id for entry in catalog.ordered_entries),
            ("capability_only", "combined", "database_only"),
        )
        self.assertEqual(
            tuple(item.pack_id for item in catalog.databases), ("combined", "database_only")
        )
        self.assertIs(catalog.get("combined"), catalog.entries_by_id["combined"])

    def test_normalized_definition_is_deeply_immutable(self) -> None:
        entry = validate_canonical_pack(FIXTURES / "combined")
        with self.assertRaises(TypeError):
            entry.definition.extensions["new"] = {}  # type: ignore[index]
        with self.assertRaises(TypeError):
            entry.definition.dependencies["python"] += ("new",)  # type: ignore[index]
        self.assertEqual(entry.definition.to_dict()["schema_version"], 2)

    def test_rejects_v1_and_flat_legacy_input(self) -> None:
        with self.assertRaises(CanonicalPackValidationError):
            validate_canonical_pack(FIXTURES / "invalid" / "legacy")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "flat"
            root.mkdir()
            (root / "pack.yaml").write_text(
                "id: flat\nname: Flat\nversion: 1.0.0\n", encoding="utf-8"
            )
            with self.assertRaises(CanonicalPackValidationError):
                validate_canonical_pack(root)

    def test_rejects_alternate_manifest_filename_and_dangling_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "alternate"
            root.mkdir()
            (root / "pack.yml").symlink_to(root / "missing-pack.yml")
            with self.assertRaises(CanonicalPackValidationError):
                BundledCatalog.from_root(Path(tmp))
    def test_legacy_loader_rejects_v2_instead_of_dropping_declarations(self) -> None:
        with self.assertRaisesRegex(PackValidationError, "legacy loading"):
            load_pack_manifest(FIXTURES / "capability_only" / "pack.yaml")


    def test_external_database_rejects_before_resource_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "external_db"
            root.mkdir()
            (root / "pack.yaml").write_text(
                """schema_version: 2
id: external_db
name: External DB
version: 1.0.0
database:
  default_enabled: false
  depends_on: []
  migrations:
    - version: 1
      name: initial
      path: missing/never-read.sql
      tables: [records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts: {}
  bridge_mounts: []
""",
                encoding="utf-8",
            )
            with patch(
                "astrid.core.pack.canonical._resolve_resources",
                side_effect=AssertionError("resources resolved"),
            ):
                for source in ExternalPackSource:
                    with self.subTest(source=source.value):
                        with self.assertRaises(ExternalDatabaseForbidden):
                            read_normalize_validate(root / "pack.yaml", source=source)

    def test_external_capability_only_is_admitted(self) -> None:
        for source in ExternalPackSource:
            with self.subTest(source=source.value):
                entry = read_normalize_validate(
                    FIXTURES / "capability_only" / "pack.yaml", source=source
                )
                self.assertEqual(entry.provenance.source, source.value)
                self.assertEqual(
                    {handle.path for handle in entry.resources},
                    {"AGENTS.md", "assets/example.txt", "executors/README.md"},
                )

    def test_rejects_non_finite_extension_values(self) -> None:
        for value in (".nan", ".inf", "-.inf"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "nonfinite"
                root.mkdir()
                (root / "pack.yaml").write_text(
                    f"""schema_version: 2
id: nonfinite
name: Nonfinite
version: 1.0.0
extensions:
  schemas:
    value: {value}
""",
                    encoding="utf-8",
                )
                with self.assertRaises(CanonicalPackValidationError):
                    validate_canonical_pack(root)

    def test_rejects_non_string_cli_mount_keys_as_canonical_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bad_mount"
            root.mkdir()
            (root / "pack.yaml").write_text(
                """schema_version: 2
id: bad_mount
name: Bad Mount
version: 1.0.0
database:
  default_enabled: false
  depends_on: []
  migrations:
    - version: 1
      name: initial
      path: migrations/0001_initial.sql
      tables: [bad_mount_records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts:
    1: records
  bridge_mounts: []
""",
                encoding="utf-8",
            )
            (root / "migrations").mkdir()
            (root / "migrations" / "0001_initial.sql").write_text(
                "SELECT 1;\n", encoding="utf-8"
            )
            with self.assertRaises(CanonicalPackValidationError):
                validate_canonical_pack(root)

    def test_rejects_duplicate_authoring_only_paths_even_with_conflicting_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "duplicate_authoring"
            root.mkdir()
            (root / "pack.yaml").write_text(
                """schema_version: 2
id: duplicate_authoring
name: Duplicate Authoring
version: 1.0.0
capabilities: [render]
authoring_only:
  - path: draft.txt
    kind: test
    reason: Test copy.
  - path: draft.txt
    kind: golden
    reason: Golden copy.
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CanonicalPackValidationError, "duplicate path"):
                validate_canonical_pack(root)

    def test_legacy_local_elements_are_not_materialized_by_canonical_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            local_root = project_root / "astrid" / "packs" / "local"
            element_root = local_root / "elements" / "effects" / "legacy"
            element_root.mkdir(parents=True)
            (element_root / "element.yaml").write_text(
                "id: legacy\n"
                "kind: effect\n"
                "pack_id: local\n"
                "metadata: {}\n"
                "schema: {}\n"
                "defaults: {}\n"
                "runtime:\n"
                "  adapter: remotion\n",
                encoding="utf-8",
            )
            before = {
                path.relative_to(project_root): path.read_bytes()
                for path in project_root.rglob("*")
                if path.is_file()
            }

            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                discovered = discover_canonical_pack_metadata(
                    project_root=project_root,
                    include_installed=False,
                )

            after = {
                path.relative_to(project_root): path.read_bytes()
                for path in project_root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(discovered, ())
            self.assertFalse((local_root / "pack.yaml").exists())
            self.assertEqual(after, before)

    def test_external_admission_uses_real_discovery_and_install_seams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            local_root = project_root / "astrid" / "packs" / "local"
            local_root.parent.mkdir(parents=True)

            def copy_fixture(destination: Path, *, pack_id: str = "capability_only") -> Path:
                shutil.copytree(FIXTURES / "capability_only", destination)
                if pack_id != "capability_only":
                    manifest = destination / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "id: capability_only", f"id: {pack_id}"
                        ),
                        encoding="utf-8",
                    )
                return destination

            copy_fixture(local_root, pack_id="local")
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                local = discover_canonical_pack_metadata(
                    project_root=project_root, include_installed=False
                )
            self.assertEqual([(item.id, item.source_kind) for item in local], [("local", "local")])
            self.assertTrue(all(item.entry.definition.schema_version == 2 for item in local))

            extra_root = root / "extra"
            copy_fixture(extra_root / "capability_only")
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                extra = discover_canonical_pack_metadata(
                    project_root=project_root,
                    extra_pack_roots=(str(extra_root),),
                    include_installed=False,
                )
            self.assertEqual(
                [(item.id, item.source_kind) for item in extra],
                [("local", "local"), ("capability_only", "extra")],
            )
            self.assertTrue(all(item.entry.database is None for item in extra))

            env_root = root / "env"
            copy_fixture(env_root / "capability_only")
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                env = discover_canonical_pack_metadata(
                    project_root=project_root, include_installed=False
                )
            self.assertEqual(
                [(item.id, item.source_kind) for item in env],
                [("local", "local"), ("capability_only", "env")],
            )

            install_source = copy_fixture(root / "install-source" / "capability_only")
            store_home = root / "installed-home"
            store = InstalledPackStore(packs_home=store_home / "packs")
            self.assertEqual(
                install_pack(
                    install_source,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                ),
                0,
            )
            record = store.get_active("capability_only")
            self.assertIsNotNone(record)
            self.assertEqual(record.schema_version, 2)
            self.assertEqual(
                store.active_revision_path("capability_only").name, "capability_only"
            )
            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                installed = discover_canonical_pack_metadata(
                    project_root=project_root, include_installed=True
                )
            installed_items = [item for item in installed if item.source_kind == "installed"]
            ordered = discover_canonical_packs_ordered(
                project_root=project_root,
                extra_pack_roots=(str(extra_root),),
                include_installed=False,
            )
            self.assertTrue(all(isinstance(entry, CanonicalPackEntry) for entry in ordered))
            self.assertEqual([entry.id for entry in ordered], ["local", "capability_only"])
            self.assertEqual([item.id for item in installed_items], ["capability_only"])
            self.assertEqual(installed_items[0].entry.definition.schema_version, 2)
            self.assertEqual(
                store.active_pack_roots(),
                (store.active_revision_path("capability_only"),),
            )

    def test_relative_store_path_preserves_custody_across_cwd_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "capability_only"
            shutil.copytree(FIXTURES / "capability_only", source)
            project_root = root / "project"
            project_root.mkdir()
            operation_root = root / "after-cwd-change"
            operation_root.mkdir()
            original_cwd = Path.cwd()
            try:
                os.chdir(root)
                store = InstalledPackStore("packs")
                with patch.dict(
                    os.environ,
                    {"ASTRID_HOME": str(root), ASTRID_PACKS_PATH_ENV: ""},
                    clear=False,
                ):
                    self.assertEqual(
                        install_pack(
                            source,
                            store=store,
                            skip_confirm=True,
                            trust_acknowledged=True,
                        ),
                        0,
                    )
                    record = store.get_active_strict("capability_only")
                    self.assertIsNotNone(record)
                    assert record is not None
                    active_root = store.active_revision_path("capability_only")
                    self.assertIsNotNone(active_root)
                    assert active_root is not None
                    self.assertEqual(
                        Path(record.install_root),
                        (root / "packs" / "capability_only").resolve(),
                    )
                    self.assertEqual(store.active_pack_roots(), (active_root,))

                    os.chdir(operation_root)
                    self.assertEqual(
                        store.get_active_strict("capability_only"), record
                    )
                    self.assertEqual(store.active_pack_roots(), (active_root,))
                    installed = discover_canonical_pack_metadata(
                        project_root=project_root, include_installed=True
                    )
                    self.assertEqual(
                        [item.id for item in installed if item.source_kind == "installed"],
                        ["capability_only"],
                    )
            finally:
                os.chdir(original_cwd)

    def test_installed_canonical_discovery_rejects_nested_active_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "capability_only"
            shutil.copytree(FIXTURES / "capability_only", source)
            store_home = root / "installed-home"
            store = InstalledPackStore(packs_home=store_home / "packs")
            self.assertEqual(
                install_pack(
                    source,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                ),
                0,
            )
            active = store.active_revision_path("capability_only")
            self.assertIsNotNone(active)
            assert active is not None
            forged = store.revisions_dir("capability_only") / "evil" / "capability_only"
            forged.parent.mkdir()
            shutil.copytree(active, forged)
            active_link = store.active_symlink_path("capability_only")
            active_link.unlink()
            active_link.symlink_to(Path("revisions") / "evil" / "capability_only")

            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                discovered = discover_canonical_pack_metadata(
                    project_root=root / "project", include_installed=True
                )
            self.assertEqual(discovered, ())
            self.assertIsNone(store.active_revision_path("capability_only"))
            self.assertEqual(store.active_pack_roots(), ())

    def test_installed_canonical_discovery_rejects_inactive_active_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "capability_only"
            shutil.copytree(FIXTURES / "capability_only", source)
            store_home = root / "installed-home"
            store = InstalledPackStore(packs_home=store_home / "packs")
            self.assertEqual(
                install_pack(
                    source,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                ),
                0,
            )
            active = store.active_revision_path("capability_only")
            self.assertIsNotNone(active)
            assert active is not None
            record_path = active / ".astrid" / "install.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["active"] = False
            record_path.write_text(json.dumps(record), encoding="utf-8")

            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                discovered = discover_canonical_pack_metadata(
                    project_root=root / "project", include_installed=True
                )
            self.assertEqual(discovered, ())
            self.assertEqual(store.active_pack_roots(), ())

    def test_installed_canonical_discovery_rejects_manifest_identity_forgery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "capability_only"
            shutil.copytree(FIXTURES / "capability_only", source)
            store_home = root / "installed-home"
            store = InstalledPackStore(packs_home=store_home / "packs")
            self.assertEqual(
                install_pack(
                    source,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                ),
                0,
            )
            active = store.active_revision_path("capability_only")
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.parent.parent.name, "capability_only")
            manifest_path = active / "pack.yaml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "id: capability_only", "id: forged"
                ),
                encoding="utf-8",
            )
            record = store.get_active("capability_only")
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record.pack_id, "capability_only")

            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                with self.assertRaisesRegex(
                    CanonicalPackValidationError, "does not match expected pack id"
                ):
                    discover_canonical_pack_metadata(
                        project_root=root / "project", include_installed=True
                    )


    def test_external_database_fails_closed_at_each_real_discovery_seam(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def write_database_pack(pack_root: Path, pack_id: str) -> None:
                pack_root.mkdir(parents=True)
                (pack_root / "pack.yaml").write_text(
                    f"""schema_version: 2
id: {pack_id}
name: External Database
version: 1.0.0
database:
  default_enabled: false
  depends_on: []
  migrations:
    - version: 1
      name: initial
      path: missing/never-read.sql
      tables: [records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts: {{}}
  bridge_mounts: []
""",
                    encoding="utf-8",
                )

            for source in (
                ExternalPackSource.LOCAL,
                ExternalPackSource.EXTRA,
                ExternalPackSource.ENV,
            ):
                with self.subTest(source=source.value):
                    case_root = root / source.value
                    project_root = case_root / "project"
                    if source is ExternalPackSource.LOCAL:
                        pack_root = project_root / "astrid" / "packs" / "local"
                        extra = ()
                        env = {ASTRID_PACKS_PATH_ENV: ""}
                        pack_id = "local"
                    elif source is ExternalPackSource.EXTRA:
                        pack_root = case_root / "extra" / "external_db"
                        extra = (str(pack_root.parent),)
                        env = {ASTRID_PACKS_PATH_ENV: ""}
                        pack_id = "external_db"
                    else:
                        pack_root = case_root / "env" / "external_db"
                        extra = ()
                        env = {ASTRID_PACKS_PATH_ENV: str(pack_root.parent)}
                        pack_id = "external_db"
                    write_database_pack(pack_root, pack_id)

                    with patch.dict(os.environ, env, clear=False):
                        with patch(
                            "astrid.core.pack.canonical._resolve_resources",
                            side_effect=AssertionError("resources resolved"),
                        ):
                            with self.assertRaises(ExternalDatabaseForbidden):
                                discover_canonical_pack_metadata(
                                    project_root=project_root,
                                    extra_pack_roots=extra,
                                    include_installed=False,
                                )

                    if source is ExternalPackSource.LOCAL:
                        with patch(
                            "astrid.core.pack.canonical._resolve_resources",
                            side_effect=AssertionError("resources resolved"),
                        ):
                            with self.assertRaises(ExternalDatabaseForbidden):
                                install_pack(
                                    pack_root,
                                    store=InstalledPackStore(
                                        packs_home=case_root / "install-db-home"
                                    ),
                                    skip_confirm=True,
                                    trust_acknowledged=True,
                                )

            astrid_home = root / "installed"
            installed_root_home = astrid_home / "packs"
            installed_store = InstalledPackStore(packs_home=installed_root_home)
            installed_root = installed_store.revisions_dir("installed_db") / "installed_db"
            write_database_pack(installed_root, "installed_db")
            installed_manifest = installed_root / "pack.yaml"
            installed_store.record_install(
                InstallRecord(
                    pack_id="installed_db",
                    name="Installed Database",
                    version="1.0.0",
                    schema_version=2,
                    source_path=str(installed_root),
                    installed_at="2024-01-01T00:00:00Z",
                    revision="installed_db",
                    install_root=str(installed_store.install_root_for("installed_db")),
                    manifest_digest=hashlib.sha256(
                        installed_manifest.read_bytes()
                    ).hexdigest(),
                    trust_summary={"schema_version": 2},
                )
            )
            installed_store.install_root_for("installed_db").mkdir(parents=True, exist_ok=True)
            installed_store.active_symlink_path("installed_db").symlink_to(
                os.path.relpath(installed_root, installed_store.install_root_for("installed_db"))
            )
            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(astrid_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                with patch(
                    "astrid.core.pack.canonical._resolve_resources",
                    side_effect=AssertionError("resources resolved"),
                ):
                    with self.assertRaises(ExternalDatabaseForbidden):
                        discover_canonical_pack_metadata(
                            project_root=root / "installed" / "project",
                            include_installed=True,
                        )
    def test_bundled_trust_cannot_be_spoofed_through_public_admission(self) -> None:
        with self.assertRaises(CanonicalPackValidationError):
            read_normalize_validate(
                FIXTURES / "combined" / "pack.yaml",
                source="bundled",  # type: ignore[arg-type]
            )
    def test_catalog_rejects_every_database_ownership_collision(self) -> None:
        collision_fields = {
            "stream_types": ["shared.stream"],
            "event_kinds": ["shared.created"],
            "command_kinds": ["shared.create"],
            "repositories": ["SharedRepository"],
            "cli_mounts": {"shared": "shared"},
            "bridge_mounts": ["shared"],
        }

        def write_database_pack(
            root: Path, pack_id: str, *, table_name: str | None = None, **overrides: object
        ) -> None:
            pack = root / pack_id
            pack.mkdir()
            database = {
                "default_enabled": True,
                "depends_on": [],
                "migrations": [
                    {
                        "version": 1,
                        "name": "initial",
                        "path": "migrations/0001_initial.sql",
                        "tables": [table_name or f"{pack_id}_records"],
                    }
                ],
                "stream_types": [],
                "event_kinds": [],
                "command_kinds": [],
                "repositories": [],
                "conformance": [],
                "cli_mounts": {},
                "bridge_mounts": [],
            }
            database.update(overrides)
            (pack / "pack.yaml").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "id": pack_id,
                        "name": pack_id,
                        "version": "1.0.0",
                        "database": database,
                    }
                ),
                encoding="utf-8",
            )
            (pack / "migrations").mkdir()
            (pack / "migrations" / "0001_initial.sql").write_text(
                f"CREATE TABLE {pack_id}_records (id TEXT PRIMARY KEY);",
                encoding="utf-8",
            )

        for field, value in collision_fields.items():
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write_database_pack(root, "alpha", **{field: value})
                    write_database_pack(root, "beta", **{field: value})
                    with self.assertRaises(CanonicalPackValidationError):
                        BundledCatalog.from_root(root)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_database_pack(root, "alpha", table_name="shared_records")
            write_database_pack(root, "beta", table_name="shared_records")
            with self.assertRaises(CanonicalPackValidationError):
                BundledCatalog.from_root(root)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "repeat"
            (pack / "migrations").mkdir(parents=True)
            (pack / "pack.yaml").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "id": "repeat",
                        "name": "repeat",
                        "version": "1.0.0",
                        "database": {
                            "default_enabled": True,
                            "depends_on": [],
                            "migrations": [
                                {
                                    "version": 1,
                                    "name": "initial",
                                    "path": "migrations/0001_initial.sql",
                                    "tables": ["repeat_records"],
                                },
                                {
                                    "version": 2,
                                    "name": "again",
                                    "path": "migrations/0002_again.sql",
                                    "tables": ["repeat_records"],
                                },
                            ],
                            "stream_types": [],
                            "event_kinds": [],
                            "command_kinds": [],
                            "repositories": [],
                            "conformance": [],
                            "cli_mounts": {},
                            "bridge_mounts": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (pack / "migrations" / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
            (pack / "migrations" / "0002_again.sql").write_text("SELECT 1;", encoding="utf-8")
            with self.assertRaises(CanonicalPackValidationError):
                BundledCatalog.from_root(root)


    def test_rejects_traversal_and_symlink_escape(self) -> None:
        with self.assertRaises(CanonicalPackValidationError):
            validate_canonical_pack(FIXTURES / "invalid" / "dependency")
        with self.assertRaises(CanonicalPackValidationError):
            validate_canonical_pack(FIXTURES / "invalid" / "traversal")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "symlinked"
            outside = Path(tmp) / "outside.txt"
            root.mkdir()
            outside.write_text("outside", encoding="utf-8")
            (root / "pack.yaml").write_text(
                "schema_version: 2\nid: symlinked\nname: Symlinked\nversion: 1.0.0\n"
                "resources:\n  - path: asset.txt\n    kind: runtime\n",
                encoding="utf-8",
            )
            (root / "asset.txt").symlink_to(outside)
            with self.assertRaises(CanonicalPackValidationError):
                validate_canonical_pack(root)

    def test_catalog_enforces_database_dependency_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for pack_id, dependency in (("base", ""), ("child", "base")):
                pack = root / pack_id
                pack.mkdir()
                dependency_block = (
                    "\n  depends_on:\n    - pack: base\n      min_migration: 2"
                    if dependency
                    else "\n  depends_on: []"
                )
                (pack / "pack.yaml").write_text(
                    f"""schema_version: 2
id: {pack_id}
name: {pack_id}
version: 1.0.0
database:
  default_enabled: true{dependency_block}
  migrations:
    - version: 1
      name: initial
      path: migrations/0001_initial.sql
      tables: [{pack_id}_records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts: {{}}
  bridge_mounts: []
""",
                    encoding="utf-8",
                )
                (pack / "migrations").mkdir()
                (pack / "migrations" / "0001_initial.sql").write_text(
                    "SELECT 1;\n", encoding="utf-8"
                )
            with self.assertRaises(CanonicalPackValidationError):
                BundledCatalog.from_root(root)

    def test_catalog_rejects_symlinked_pack_directory_before_bundled_admission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "catalog"
            outside = Path(tmp) / "linked"
            root.mkdir()
            outside.mkdir()
            (outside / "pack.yaml").write_text(
                """schema_version: 2
id: linked
name: Linked
version: 1.0.0
database:
  default_enabled: true
  depends_on: []
  migrations:
    - version: 1
      name: initial
      path: migrations/0001_initial.sql
      tables: [linked_records]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts: {}
  bridge_mounts: []
""",
                encoding="utf-8",
            )
            (root / "linked").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(
                CanonicalPackValidationError, "bundled pack directory must not be a symlink"
            ):
                BundledCatalog.from_root(root)

    def test_normalization_rejects_duplicate_database_dependency_pack_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "duplicate_deps"
            (root / "migrations").mkdir(parents=True)
            (root / "migrations" / "0001_initial.sql").write_text(
                "SELECT 1;\n", encoding="utf-8"
            )

            def write_manifest(depends_on: list[dict[str, int]]) -> None:
                (root / "pack.yaml").write_text(
                    json.dumps(
                        {
                            "schema_version": 2,
                            "id": "duplicate_deps",
                            "name": "Duplicate Dependencies",
                            "version": "1.0.0",
                            "database": {
                                "default_enabled": True,
                                "depends_on": depends_on,
                                "migrations": [
                                    {
                                        "version": 1,
                                        "name": "initial",
                                        "path": "migrations/0001_initial.sql",
                                        "tables": ["duplicate_deps_records"],
                                    }
                                ],
                                "stream_types": [],
                                "event_kinds": [],
                                "command_kinds": [],
                                "repositories": [],
                                "conformance": [],
                                "cli_mounts": {},
                                "bridge_mounts": [],
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            write_manifest(
                [{"pack": "base", "min_migration": 1}, {"pack": "base", "min_migration": 1}]
            )
            with self.assertRaises(CanonicalPackValidationError):
                validate_canonical_pack(root)

            write_manifest(
                [{"pack": "base", "min_migration": 1}, {"pack": "base", "min_migration": 2}]
            )
            with self.assertRaisesRegex(
                CanonicalPackValidationError,
                "database\\.depends_on contains duplicate pack ID 'base'",
            ):
                validate_canonical_pack(root)

    def test_resource_directory_excludes_authoring_only_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "authoring"
            (root / "content" / "drafts" / "nested").mkdir(parents=True)
            (root / "content" / "runtime.txt").write_text("runtime", encoding="utf-8")
            (root / "content" / "drafts" / "notes.txt").write_text("draft", encoding="utf-8")
            (root / "content" / "drafts" / "nested" / "secret.txt").write_text(
                "secret", encoding="utf-8"
            )
            (root / "pack.yaml").write_text(
                """schema_version: 2
id: authoring
name: Authoring
version: 1.0.0
content:
  docs: content
authoring_only:
  - path: content/drafts
    kind: authoring_document
    reason: Draft material is not runtime content.
""",
                encoding="utf-8",
            )

            entry = validate_canonical_pack(root)
            self.assertEqual({handle.path for handle in entry.resources}, {"content/runtime.txt"})

    def test_explicit_runtime_leaf_cannot_also_be_authoring_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ambiguous"
            root.mkdir()
            (root / "runtime.txt").write_text("runtime", encoding="utf-8")
            (root / "pack.yaml").write_text(
                """schema_version: 2
id: ambiguous
name: Ambiguous
version: 1.0.0
resources:
  - path: runtime.txt
    kind: runtime
authoring_only:
  - path: runtime.txt
    kind: authoring_document
    reason: This declaration is ambiguous.
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CanonicalPackValidationError, "overlaps authoring-only path"
            ):
                validate_canonical_pack(root)

    def test_documentation_none_requires_another_contribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            only_opt_out = Path(tmp) / "only_opt_out"
            only_opt_out.mkdir()
            (only_opt_out / "pack.yaml").write_text(
                """schema_version: 2
id: only_opt_out
name: Only Opt Out
version: 1.0.0
documentation:
  kind: none
  reason: Documentation is intentionally omitted.
""",
                encoding="utf-8",
            )
            with self.assertRaises(CanonicalPackValidationError):
                validate_canonical_pack(only_opt_out)

            real_pack = Path(tmp) / "real_pack"
            real_pack.mkdir()
            (real_pack / "pack.yaml").write_text(
                """schema_version: 2
id: real_pack
name: Real Pack
version: 1.0.0
capabilities: [render]
documentation:
  kind: none
  reason: Documentation is intentionally omitted.
""",
                encoding="utf-8",
            )
            entry = validate_canonical_pack(real_pack)
            self.assertIsNotNone(entry.documentation)
            self.assertEqual(entry.documentation.kind, "none")

    def test_rejects_symlinked_external_pack_roots_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "linked-target"
            target.mkdir()
            (target / "pack.yaml").write_text(
                "schema_version: 2\nid: linked\nname: Linked\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )

            direct_link = root / "direct-link"
            direct_link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(CanonicalPackValidationError, "must not be a symlink"):
                validate_canonical_pack(direct_link)

            for source in (ExternalPackSource.EXTRA, ExternalPackSource.ENV):
                with self.subTest(source=source.value):
                    case_root = root / source.value
                    source_root = case_root / "packs"
                    source_root.mkdir(parents=True)
                    source_link = source_root / "linked"
                    source_link.symlink_to(target, target_is_directory=True)
                    env = {
                        ASTRID_PACKS_PATH_ENV: str(source_root)
                        if source is ExternalPackSource.ENV
                        else ""
                    }
                    extra = (str(source_root),) if source is ExternalPackSource.EXTRA else ()
                    with patch.dict(os.environ, env, clear=False):
                        with self.assertRaisesRegex(
                            CanonicalPackValidationError, "must not be a symlink"
                        ):
                            discover_canonical_pack_metadata(
                                project_root=case_root / "project",
                                extra_pack_roots=extra,
                                include_installed=False,
                            )

            local_project = root / "local-project"
            local_packs = local_project / "astrid" / "packs"
            local_packs.mkdir(parents=True)
            local_packs.joinpath("local").symlink_to(target, target_is_directory=True)
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                with self.assertRaisesRegex(CanonicalPackValidationError, "must not be a symlink"):
                    discover_canonical_pack_metadata(
                        project_root=local_project, include_installed=False
                    )

            with self.assertRaisesRegex(CanonicalPackValidationError, "must not be a symlink"):
                install_pack(
                    direct_link,
                    store=InstalledPackStore(packs_home=root / "install-home"),
                    skip_confirm=True,
                    trust_acknowledged=True,
                )

            installed_home = root / "installed-home"
            installed_store = InstalledPackStore(packs_home=installed_home)
            installed_root = installed_store.revisions_dir("linked") / "linked"
            installed_root.parent.mkdir(parents=True)
            installed_root.symlink_to(target, target_is_directory=True)
            installed_store.install_root_for("linked").mkdir(parents=True, exist_ok=True)
            installed_store.active_symlink_path("linked").symlink_to(
                os.path.relpath(installed_root, installed_store.install_root_for("linked"))
            )
            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(installed_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                discovered = discover_canonical_pack_metadata(
                    project_root=root / "installed-project", include_installed=True
                )
            self.assertEqual(discovered, ())

    def test_rejects_recursive_yaml_aliases_and_preserves_shared_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aliases"
            root.mkdir()
            manifest = root / "pack.yaml"
            manifest.write_text(
                """schema_version: 2
id: aliases
name: Aliases
version: 1.0.0
capabilities: [render]
extensions:
  schemas: &loop
    self: *loop
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CanonicalPackValidationError, "recursive YAML alias"):
                validate_canonical_pack(root)

            manifest.write_text(
                """schema_version: 2
id: aliases
name: Aliases
version: 1.0.0
capabilities: [render]
extensions:
  schemas:
    first: &schema
      type: string
    second: *schema
""",
                encoding="utf-8",
            )
            entry = validate_canonical_pack(root)
            self.assertEqual(
                entry.extensions["schemas"]["first"],
                {"type": "string"},
            )
            self.assertEqual(
                entry.extensions["schemas"]["second"],
                {"type": "string"},
            )

    def test_reserves_pack_yaml_from_all_declared_resource_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "reserved"
            root.mkdir()
            base = {
                "schema_version": 2,
                "id": "reserved",
                "name": "Reserved",
                "version": "1.0.0",
                "capabilities": ["render"],
            }
            declarations = (
                {"resources": [{"path": "pack.yaml", "kind": "runtime"}]},
                {
                    "authoring_only": [
                        {
                            "path": "pack.yaml",
                            "kind": "authoring_document",
                            "reason": "Manifest is not authoring content.",
                        }
                    ]
                },
                {"content": {"docs": "pack.yaml"}},
            )
            for declaration in declarations:
                with self.subTest(declaration=declaration):
                    (root / "pack.yaml").write_text(
                        json.dumps({**base, **declaration}),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(CanonicalPackValidationError, "pack.yaml"):
                        validate_canonical_pack(root)


    def test_rejects_symlinked_pack_ancestors_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real_parent = base / "real" / "packs"
            pack_root = real_parent / "direct"
            pack_root.mkdir(parents=True)
            (pack_root / "pack.yaml").write_text(
                "schema_version: 2\nid: direct\nname: Direct\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            symlink_parent = base / "linked"
            symlink_parent.symlink_to(real_parent.parent, target_is_directory=True)
            supplied = symlink_parent / "packs" / "direct"
            with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                validate_canonical_pack(supplied)

    def test_rejects_symlinked_local_extra_and_environment_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project_root = base / "project"
            project_root.mkdir()
            real_extra = base / "real-extra"
            (real_extra / "extra_pack").mkdir(parents=True)
            (real_extra / "extra_pack" / "pack.yaml").write_text(
                "schema_version: 2\nid: extra_pack\nname: Extra\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            linked_extra = base / "linked-extra"
            linked_extra.symlink_to(real_extra, target_is_directory=True)
            with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                discover_canonical_pack_metadata(
                    project_root=project_root,
                    extra_pack_roots=(str(linked_extra),),
                    include_installed=False,
                )
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(linked_extra)}, clear=False):
                with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                    discover_canonical_pack_metadata(
                        project_root=project_root, include_installed=False
                    )

            outside_local = base / "outside-local"
            elements = outside_local / "elements" / "effects" / "demo"
            elements.mkdir(parents=True)
            (elements / "element.yaml").write_text("{}", encoding="utf-8")
            local_root = project_root / "astrid" / "packs" / "local"
            local_root.parent.mkdir(parents=True)
            local_root.symlink_to(outside_local, target_is_directory=True)
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                    discover_canonical_pack_metadata(
                        project_root=project_root, include_installed=False
                    )
            self.assertFalse((outside_local / "pack.yaml").exists())

    def test_rejects_symlinked_ancestors_for_external_seams_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real_container = base / "real-container"
            real_scan_root = real_container / "packs"
            pack_root = real_scan_root / "ancestor_pack"
            pack_root.mkdir(parents=True)
            (pack_root / "pack.yaml").write_text(
                "schema_version: 2\nid: ancestor_pack\nname: Ancestor\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            linked_container = base / "linked-container"
            linked_container.symlink_to(real_container, target_is_directory=True)
            linked_scan_root = linked_container / "packs"
            project_root = base / "project"
            project_root.mkdir()

            with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                validate_canonical_pack(linked_scan_root / "ancestor_pack")
            with self.assertRaisesRegex(CanonicalPackValidationError, "must not be a symlink"):
                install_pack(
                    linked_scan_root / "ancestor_pack",
                    store=InstalledPackStore(packs_home=base / "install-home"),
                    skip_confirm=True,
                    trust_acknowledged=True,
                )
            with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                discover_canonical_pack_metadata(
                    project_root=project_root,
                    extra_pack_roots=(str(linked_scan_root),),
                    include_installed=False,
                )
            with patch.dict(
                os.environ,
                {ASTRID_PACKS_PATH_ENV: str(linked_scan_root)},
                clear=False,
            ):
                with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                    discover_canonical_pack_metadata(
                        project_root=project_root, include_installed=False
                    )

            real_project = base / "real-project"
            local_pack = real_project / "astrid" / "packs" / "local"
            local_pack.mkdir(parents=True)
            (local_pack / "pack.yaml").write_text(
                "schema_version: 2\nid: local\nname: Local\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            linked_project = base / "linked-project"
            linked_project.symlink_to(real_project, target_is_directory=True)
            with patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                    discover_canonical_pack_metadata(
                        project_root=linked_project, include_installed=False
                    )

    def test_rejects_symlinked_child_pack_and_catalog_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            scan_root = base / "scan"
            scan_root.mkdir()
            outside_pack = base / "outside-pack"
            outside_pack.mkdir()
            (outside_pack / "pack.yaml").write_text(
                "schema_version: 2\nid: linked\nname: Linked\nversion: 1.0.0\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            (scan_root / "linked").symlink_to(outside_pack, target_is_directory=True)
            with self.assertRaisesRegex(CanonicalPackValidationError, "symlink"):
                discover_canonical_pack_metadata(
                    project_root=base / "project",
                    extra_pack_roots=(str(scan_root),),
                    include_installed=False,
                )

            catalog_target = base / "catalog-target"
            catalog_target.mkdir()
            catalog_link = base / "catalog-link"
            catalog_link.symlink_to(catalog_target, target_is_directory=True)
            with self.assertRaisesRegex(CanonicalPackValidationError, "catalog root.*symlink"):
                BundledCatalog.from_root(catalog_link)

    def test_resource_symlink_is_rejected_before_candidate_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "resource_pack"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "pack.yaml").write_text(
                "schema_version: 2\nid: resource_pack\nname: Resources\nversion: 1.0.0\n"
                "resources:\n  - path: asset.txt\n    kind: runtime\n",
                encoding="utf-8",
            )
            candidate = root / "asset.txt"
            candidate.symlink_to(outside)
            original_resolve = Path.resolve

            def resolve(path: Path, *args: object, **kwargs: object) -> Path:
                if path == candidate:
                    raise AssertionError("resource resolve preceded symlink rejection")
                return original_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=resolve):
                with self.assertRaises(CanonicalPackValidationError):
                    validate_canonical_pack(root)
    def test_install_rejects_external_manifest_symlink_before_read_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "candidate"
            source.mkdir()
            external_manifest = root / "external-pack.yaml"
            external_manifest.write_text(
                "schema_version: 2\n"
                "id: external_manifest_read\n"
                "name: External\n"
                "version: 9.9.9\n"
                "capabilities: [render]\n",
                encoding="utf-8",
            )
            manifest = source / "pack.yaml"
            manifest.symlink_to(external_manifest)
            store_home = root / "packs"
            store_home.mkdir()
            store = InstalledPackStore(packs_home=store_home)
            before_source = _snapshot_tree(source)
            before_store = _snapshot_tree(store_home)
            before_external = external_manifest.read_bytes()
            read_paths: list[Path] = []
            original_read_text = Path.read_text

            def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
                read_paths.append(path)
                if path.resolve() == external_manifest.resolve():
                    raise AssertionError("external manifest was read before custody rejection")
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", autospec=True, side_effect=guarded_read_text):
                with self.assertRaises(CanonicalPackValidationError):
                    install_pack(
                        source,
                        store=store,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    )

            self.assertEqual(_snapshot_tree(source), before_source)
            self.assertEqual(_snapshot_tree(store_home), before_store)
            self.assertEqual(external_manifest.read_bytes(), before_external)
    def test_canonical_update_rejects_symlinked_legacy_source_without_read_or_mutation(
        self,
    ) -> None:
        """Canonical lifecycle never falls back through an attacker source."""
        for filename, content in (
            (
                "pack.yml",
                "schema_version: 1\nid: capability_only\nname: External\nversion: 9.9.9\n",
            ),
            (
                "pack.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "capability_only",
                        "name": "External",
                        "version": "9.9.9",
                    }
                ),
            ),
            (
                "pack.yml",
                "id: capability_only\nname: External\nversion: 9.9.9\n",
            ),
        ):
            with self.subTest(filename=filename, content=content):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root / "source" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    store = InstalledPackStore(packs_home=root / "packs")
                    install_args = {
                        "store": store,
                        "skip_confirm": True,
                        "trust_acknowledged": True,
                    }
                    self.assertEqual(install_pack(source, **install_args), 0)
                    before_store = _snapshot_tree(root / "packs")

                    source.rename(root / "canonical-source")
                    external = root / "external"
                    external.mkdir()
                    external_manifest = external / filename
                    external_manifest.write_text(content, encoding="utf-8")
                    source.symlink_to(external, target_is_directory=True)
                    before_external = external_manifest.read_bytes()
                    read_paths: list[Path] = []
                    original_read_text = Path.read_text

                    def guarded_read_text(
                        path: Path, *args: object, **kwargs: object
                    ) -> str:
                        read_paths.append(path)
                        if path.resolve() == external_manifest.resolve():
                            raise AssertionError("external legacy manifest was read")
                        return original_read_text(path, *args, **kwargs)

                    with patch.object(
                        Path,
                        "read_text",
                        autospec=True,
                        side_effect=guarded_read_text,
                    ):
                        result = update_pack(
                            "capability_only",
                            store=store,
                            skip_confirm=True,
                            trust_acknowledged=True,
                        )

                    self.assertEqual(result, 2)
                    self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                    self.assertEqual(external_manifest.read_bytes(), before_external)
                    self.assertNotIn(
                        external_manifest.resolve(),
                        {path.resolve() for path in read_paths},
                    )

            self.assertNotIn(
                external_manifest.resolve(),
                {path.resolve() for path in read_paths},
            )

    def test_canonical_local_update_non_v2_manifest_is_read_only(self) -> None:
        """Canonical local updates reject every non-v2 replacement in place."""
        cases = (
            ("v1", "schema_version: 1\nid: capability_only\nname: Legacy\nversion: 9.9.9\n"),
            ("schema-less", "id: capability_only\nname: Legacy\nversion: 9.9.9\n"),
            ("unknown", "schema_version: 99\nid: capability_only\nname: Unknown\nversion: 9.9.9\n"),
        )
        for label, content in cases:
            for dry_run in (False, True):
                with self.subTest(label=label, dry_run=dry_run), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root / "source" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    store = InstalledPackStore(packs_home=root / "packs")
                    install_args = {
                        "store": store,
                        "skip_confirm": True,
                        "trust_acknowledged": True,
                    }
                    self.assertEqual(install_pack(source, **install_args), 0)
                    existing = store.get_active_strict("capability_only")
                    self.assertIsNotNone(existing)
                    assert existing is not None
                    before_store = _snapshot_tree(root / "packs")
                    before_source_path = existing.source_path
                    before_active = store.active_revision_path("capability_only")
                    self.assertIsNotNone(before_active)
                    assert before_active is not None
                    before_record = (before_active / ".astrid" / "install.json").read_bytes()
                    (source / "pack.yaml").write_text(content, encoding="utf-8")

                    with (
                        patch(
                            "astrid.core.pack.install_local.load_manifest_for_dispatch",
                            side_effect=AssertionError("canonical update used dispatch parser"),
                        ),
                        patch(
                            "astrid.core.pack.install_local.validate_pack",
                            side_effect=AssertionError("canonical update used legacy validator"),
                        ),
                        patch(
                            "astrid.core.pack.install_local.extract_trust_summary",
                            side_effect=AssertionError("canonical update used legacy summary"),
                        ),
                    ):
                        result = update_pack(
                            "capability_only",
                            store=store,
                            dry_run=dry_run,
                            skip_confirm=True,
                            trust_acknowledged=True,
                        )

                    self.assertEqual(result, 2)
                    self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                    after = store.get_active_strict("capability_only")
                    self.assertIsNotNone(after)
                    assert after is not None
                    self.assertEqual(after.source_path, before_source_path)
                    active_after = store.active_revision_path("capability_only")
                    self.assertIsNotNone(active_after)
                    assert active_after is not None
                    self.assertEqual(
                        (active_after / ".astrid" / "install.json").read_bytes(),
                        before_record,
                    )
                    self.assertFalse(store.staging_path_for("capability_only").exists())

    def test_paired_metadata_downgrade_rejects_local_update_before_source_reads(
        self,
    ) -> None:
        """Both stored discriminators cannot downgrade an installed v2 tree."""
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                store = InstalledPackStore(packs_home=root / "packs")
                self.assertEqual(
                    install_pack(
                        source,
                        store=store,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    ),
                    0,
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                record_path = active / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["schema_version"] = 1
                record["trust_summary"]["schema_version"] = 1
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                before_store = _snapshot_tree(root / "packs")
                source_root = source.resolve()
                original_read_text = Path.read_text

                def guarded_read_text(
                    path: Path, *args: object, **kwargs: object
                ) -> str:
                    if path.resolve().is_relative_to(source_root):
                        raise AssertionError("local update read external source")
                    return original_read_text(path, *args, **kwargs)

                with patch.object(
                    Path, "read_text", autospec=True, side_effect=guarded_read_text
                ):
                    with self.assertRaises(AstridError):
                        update_pack(
                            "capability_only",
                            store=store,
                            dry_run=dry_run,
                            skip_confirm=True,
                            trust_acknowledged=True,
                        )
                self.assertEqual(_snapshot_tree(root / "packs"), before_store)

    def test_paired_metadata_downgrade_rejects_rollback_before_target_read(
        self,
    ) -> None:
        """Current and target records cannot cross-dispatch a canonical rollback."""
        for tampered in ("current", "target"):
            with self.subTest(tampered=tampered), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source
                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args), 0
                )
                target_name = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                target = store.revisions_dir("capability_only") / target_name
                tampered_root = active if tampered == "current" else target
                record_path = tampered_root / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["schema_version"] = 1
                record["trust_summary"]["schema_version"] = 1
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                before_store = _snapshot_tree(root / "packs")
                target_manifest = target / "pack.yaml"
                original_read_text = Path.read_text

                def guarded_read_text(
                    path: Path, *args: object, **kwargs: object
                ) -> str:
                    if path.resolve() == target_manifest.resolve():
                        raise AssertionError("rollback target manifest was read")
                    return original_read_text(path, *args, **kwargs)

                with patch.object(
                    Path, "read_text", autospec=True, side_effect=guarded_read_text
                ):
                    with self.assertRaises(AstridError):
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_name,
                            skip_confirm=True,
                        )
                self.assertEqual(_snapshot_tree(root / "packs"), before_store)

    def test_canonical_update_rejects_malformed_installed_schema_before_source_reads(
        self,
    ) -> None:
        """A canonical record cannot be downgraded by one bad discriminator."""
        cases = (
            ("string", "2"),
            ("boolean", True),
            ("float", 2.0),
            ("null", None),
            ("missing", None),
            ("unsupported", 99),
            ("contradictory", 1),
        )
        for label, value in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                store = InstalledPackStore(packs_home=root / "packs")
                self.assertEqual(
                    install_pack(
                        source,
                        store=store,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    ),
                    0,
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                record_path = active / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if label == "missing":
                    del record["schema_version"]
                else:
                    record["schema_version"] = value
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                before_store = _snapshot_tree(root / "packs")
                before_active = store.active_symlink_path("capability_only").readlink()
                source_root = source.resolve()
                original_read_text = Path.read_text

                def guarded_read_text(
                    path: Path, *args: object, **kwargs: object
                ) -> str:
                    if path.resolve().is_relative_to(source_root):
                        raise AssertionError("canonical source was read before custody rejection")
                    return original_read_text(path, *args, **kwargs)

                for dry_run in (False, True):
                    with patch.object(
                        Path, "read_text", autospec=True, side_effect=guarded_read_text
                    ):
                        with self.assertRaises(AstridError):
                            update_pack(
                                "capability_only",
                                store=store,
                                dry_run=dry_run,
                                skip_confirm=True,
                                trust_acknowledged=True,
                            )
                    self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                    self.assertEqual(
                        store.active_symlink_path("capability_only").readlink(),
                        before_active,
                    )

    def test_canonical_rollback_rejects_malformed_target_schema_before_publication(
        self,
    ) -> None:
        """A requested canonical target is admitted before manifest dispatch."""
        cases = (
            ("string", "2"),
            ("boolean", True),
            ("float", 2.0),
            ("null", None),
            ("missing", None),
            ("unsupported", 99),
            ("contradictory", 1),
        )
        for label, value in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source
                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args),
                    0,
                )
                target_name = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                target_path = store.revisions_dir("capability_only") / target_name
                record_path = target_path / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if label == "missing":
                    del record["schema_version"]
                else:
                    record["schema_version"] = value
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                before_store = _snapshot_tree(root / "packs")
                before_active = store.active_symlink_path("capability_only").readlink()
                target_manifest = target_path / "pack.yaml"
                original_read_text = Path.read_text

                def guarded_read_text(
                    path: Path, *args: object, **kwargs: object
                ) -> str:
                    if path.resolve() == target_manifest.resolve():
                        raise AssertionError("rollback target manifest was read before custody rejection")
                    return original_read_text(path, *args, **kwargs)

                with patch.object(
                    Path, "read_text", autospec=True, side_effect=guarded_read_text
                ):
                    with self.assertRaises(AstridError):
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_name,
                            skip_confirm=True,
                        )
                self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                self.assertEqual(
                    store.active_symlink_path("capability_only").readlink(),
                    before_active,
                )

    def test_canonical_install_rejects_direct_revision_symlink_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_id = "capability_only"
            store = InstalledPackStore(packs_home=root / "packs")
            revisions = store.revisions_dir(pack_id)
            revisions.mkdir(parents=True)
            target = revisions / pack_id

            external = root / "external-revision"
            external_metadata = external / ".astrid"
            external_metadata.mkdir(parents=True)
            external_record = InstallRecord(
                pack_id=pack_id,
                name="External",
                version="9.9.9",
                schema_version=2,
                source_path="external",
                installed_at="2026-01-01T00:00:00Z",
                revision=pack_id,
                install_root=str(store.install_root_for(pack_id)),
            )
            external_record_path = external_metadata / "install.json"
            external_record_path.write_text(
                json.dumps(external_record.to_dict(), indent=2),
                encoding="utf-8",
            )
            external_sentinel = external / "sentinel.txt"
            external_sentinel.write_bytes(b"external bytes stay untouched")
            target.symlink_to(external, target_is_directory=True)

            staging = store.staging_path_for(pack_id)
            staging.mkdir()
            (staging / "leftover.tmp").write_bytes(b"staging stays untouched")
            before_pack = _snapshot_tree(store.install_root_for(pack_id))
            before_record = external_record_path.read_bytes()
            before_sentinel = external_sentinel.read_bytes()

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = install_pack(
                    FIXTURES / pack_id,
                    store=store,
                    skip_confirm=True,
                    trust_acknowledged=True,
                    trust_method="test",
                    trust_actor="test",
                )

            self.assertEqual(result, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("symlinked", stderr.getvalue())
            self.assertEqual(_snapshot_tree(store.install_root_for(pack_id)), before_pack)
            self.assertEqual(external_record_path.read_bytes(), before_record)
            self.assertEqual(external_sentinel.read_bytes(), before_sentinel)
            self.assertEqual(
                sorted(path.name for path in revisions.iterdir()),
                [pack_id],
            )
            self.assertTrue(target.is_symlink())

    def test_canonical_timestamped_rollback_then_force_keeps_single_active_revision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources: dict[str, Path] = {}
            for version in ("1.0.0", "2.0.0", "3.0.0"):
                source = root / f"source-{version}" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                manifest = source / "pack.yaml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        "version: 1.0.0", f"version: {version}"
                    ),
                    encoding="utf-8",
                )
                sources[version] = source

            store = InstalledPackStore(packs_home=root / "packs")
            install_args = {
                "store": store,
                "skip_confirm": True,
                "trust_acknowledged": True,
            }
            self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
            self.assertEqual(
                install_pack(sources["2.0.0"], force=True, **install_args), 0
            )

            rollback_revision = next(
                path.name
                for path in store.list_revisions("capability_only")
                if path.name != "capability_only"
            )
            self.assertEqual(
                rollback_pack(
                    "capability_only",
                    store=store,
                    revision=rollback_revision,
                    skip_confirm=True,
                ),
                0,
            )
            active = store.get_active_strict("capability_only")
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.version, "1.0.0")
            active_root = store.active_revision_path("capability_only")
            self.assertIsNotNone(active_root)
            assert active_root is not None
            self.assertEqual(active_root.name, rollback_revision)
            self.assertEqual(store.active_pack_roots(), (active_root,))

            self.assertEqual(
                install_pack(sources["3.0.0"], force=True, **install_args), 0
            )
            active = store.get_active_strict("capability_only")
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.version, "3.0.0")
            self.assertEqual(active.revision, "capability_only")
            roots = store.active_pack_roots()
            self.assertEqual(roots, (store.active_revision_path("capability_only"),))
            self.assertEqual(len(roots), 1)
            self.assertFalse(
                store._read_revision_record(
                    "capability_only", rollback_revision
                ).active
            )

    def test_canonical_rollback_accepts_inactive_direct_revision_after_timestamped_rollback(
        self,
    ) -> None:
        """A rotated direct revision remains an eligible rollback target."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources: dict[str, Path] = {}
            for version in ("1.0.0", "2.0.0"):
                source = root / f"source-{version}" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                manifest = source / "pack.yaml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        "version: 1.0.0", f"version: {version}"
                    ),
                    encoding="utf-8",
                )
                sources[version] = source

            store = InstalledPackStore(packs_home=root / "packs")
            install_args = {
                "store": store,
                "skip_confirm": True,
                "trust_acknowledged": True,
            }
            self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
            self.assertEqual(
                install_pack(sources["2.0.0"], force=True, **install_args),
                0,
            )

            timestamped_revision = next(
                path.name
                for path in store.list_revisions("capability_only")
                if path.name != "capability_only"
            )
            self.assertEqual(
                rollback_pack(
                    "capability_only",
                    store=store,
                    revision=timestamped_revision,
                    skip_confirm=True,
                ),
                0,
            )

            active_link = store.active_symlink_path("capability_only")
            direct_root = store.revisions_dir("capability_only") / "capability_only"
            direct_record_path = direct_root / ".astrid" / "install.json"
            direct_record = store._read_revision_record(
                "capability_only", "capability_only"
            )
            self.assertIsNotNone(direct_record)
            assert direct_record is not None
            self.assertFalse(direct_record.active)
            before_pointer = active_link.readlink()
            before_direct_record = direct_record_path.read_bytes()
            before_store = _snapshot_tree(root / "packs")
            self.assertEqual(
                before_pointer,
                Path("revisions") / timestamped_revision,
            )

            self.assertEqual(
                rollback_pack(
                    "capability_only",
                    store=store,
                    revision="capability_only",
                    skip_confirm=True,
                ),
                0,
            )

            self.assertNotEqual(active_link.readlink(), before_pointer)
            self.assertEqual(
                active_link.readlink(),
                Path("revisions") / "capability_only",
            )
            self.assertNotEqual(
                direct_record_path.read_bytes(),
                before_direct_record,
            )
            self.assertNotEqual(_snapshot_tree(root / "packs"), before_store)
            active_record = store.get_active_strict("capability_only")
            self.assertIsNotNone(active_record)
            assert active_record is not None
            self.assertEqual(active_record.revision, "capability_only")
            self.assertTrue(active_record.active)
            timestamped_record = store._read_revision_record(
                "capability_only", timestamped_revision
            )
            self.assertIsNotNone(timestamped_record)
            assert timestamped_record is not None
            self.assertFalse(timestamped_record.active)

    def test_canonical_rollback_rejects_active_manifest_without_custody_metadata(
        self,
    ) -> None:
        """Missing exact active manifests fail before rollback enumeration."""
        for manifest_state in ("missing", "alternate"):
            with self.subTest(manifest_state=manifest_state), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source

                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(
                    install_pack(sources["1.0.0"], **install_args),
                    0,
                )
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args),
                    0,
                )
                target_revision = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )

                active_root = store.active_revision_path("capability_only")
                self.assertIsNotNone(active_root)
                assert active_root is not None
                active_manifest = active_root / "pack.yaml"
                if manifest_state == "missing":
                    active_manifest.unlink()
                else:
                    active_manifest.rename(active_root / "pack.yml")
                record_path = active_root / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["manifest_digest"] = ""
                record["trust_summary"] = {}
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

                active_link = store.active_symlink_path("capability_only")
                before_pointer = active_link.readlink()
                before_store = _snapshot_tree(root / "packs")
                with patch.object(
                    store,
                    "list_revisions",
                    wraps=store.list_revisions,
                ) as list_revisions:
                    with self.assertRaises(AstridError) as raised:
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_revision,
                            skip_confirm=True,
                        )

                self.assertEqual(raised.exception.code, "pack.active_corrupt")
                list_revisions.assert_not_called()
                self.assertEqual(active_link.readlink(), before_pointer)
                self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                self.assertEqual(
                    store.active_revision_path("capability_only"),
                    active_root,
                )
                self.assertFalse(active_manifest.exists())
                if manifest_state == "alternate":
                    self.assertTrue((active_root / "pack.yml").is_file())

    def test_installed_canonical_discovery_rejects_erased_byte_custody(self) -> None:
        """Erased canonical custody cannot admit modified installed bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "capability_only"
            _copy_fixture_files(FIXTURES / "capability_only", source)
            store_home = root / "installed-home"
            store = InstalledPackStore(packs_home=store_home / "packs")
            install_args = {
                "store": store,
                "skip_confirm": True,
                "trust_acknowledged": True,
            }
            self.assertEqual(install_pack(source, **install_args), 0)
            active_root = store.active_revision_path("capability_only")
            self.assertIsNotNone(active_root)
            assert active_root is not None
            manifest_path = active_root / "pack.yaml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "capabilities: [render]", "capabilities: [forged]"
                ),
                encoding="utf-8",
            )
            modified_manifest_bytes = manifest_path.read_bytes()
            record_path = active_root / ".astrid" / "install.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["manifest_digest"] = ""
            record["trust_summary"] = {}
            record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            before_pointer = store.active_symlink_path("capability_only").readlink()
            before_store = _snapshot_tree(store_home / "packs")

            with patch.dict(
                os.environ,
                {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                clear=False,
            ):
                discovered = discover_canonical_pack_metadata(
                    project_root=root / "project", include_installed=True
                )

            self.assertEqual(discovered, ())
            self.assertEqual(store.list_installed(), [])
            self.assertEqual(store.active_pack_roots(), ())
            self.assertEqual(
                store.active_symlink_path("capability_only").readlink(),
                before_pointer,
            )
            self.assertEqual(_snapshot_tree(store_home / "packs"), before_store)
            self.assertEqual(manifest_path.read_bytes(), modified_manifest_bytes)

    def test_canonical_rollback_rejects_erased_byte_custody_before_publication(
        self,
    ) -> None:
        """Erased current or target custody cannot change the active pointer."""
        for tampered in ("current", "target"):
            with self.subTest(tampered=tampered), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source

                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args),
                    0,
                )
                target_revision = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                active_root = store.active_revision_path("capability_only")
                self.assertIsNotNone(active_root)
                assert active_root is not None
                target_root = store.revisions_dir("capability_only") / target_revision
                tampered_root = active_root if tampered == "current" else target_root
                tampered_manifest = tampered_root / "pack.yaml"
                tampered_manifest.write_text(
                    tampered_manifest.read_text(encoding="utf-8").replace(
                        "capabilities: [render]", "capabilities: [forged]"
                    ),
                    encoding="utf-8",
                )
                modified_manifest_bytes = tampered_manifest.read_bytes()
                record_path = tampered_root / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["manifest_digest"] = ""
                record["trust_summary"] = {}
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                active_link = store.active_symlink_path("capability_only")
                before_pointer = active_link.readlink()
                before_store = _snapshot_tree(root / "packs")

                with patch.object(
                    store, "list_revisions", wraps=store.list_revisions
                ) as list_revisions:
                    with self.assertRaises(AstridError) as raised:
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_revision,
                            skip_confirm=True,
                        )

                self.assertEqual(raised.exception.code, "pack.active_corrupt")
                list_revisions.assert_not_called()
                self.assertEqual(active_link.readlink(), before_pointer)
                self.assertEqual(
                    tampered_manifest.read_bytes(),
                    modified_manifest_bytes,
                )

    def test_canonical_rollback_non_v2_target_rejects_before_publication(self) -> None:
        """Canonical rollback never validates a target through the v1 path."""
        cases = (
            ("v1", "schema_version: 1\nid: capability_only\nname: Legacy\nversion: 9.9.9\n"),
            ("schema-less", "id: capability_only\nname: Legacy\nversion: 9.9.9\n"),
            ("unknown", "schema_version: 99\nid: capability_only\nname: Unknown\nversion: 9.9.9\n"),
        )
        for label, content in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source

                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args), 0
                )
                target_name = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                target_path = store.revisions_dir("capability_only") / target_name
                target_manifest = target_path / "pack.yaml"
                target_manifest.write_text(content, encoding="utf-8")
                before_store = _snapshot_tree(root / "packs")
                before_active = store.active_symlink_path("capability_only").readlink()

                with (
                    patch(
                        "astrid.core.pack.install_local.load_manifest_for_dispatch",
                        side_effect=AssertionError("canonical rollback used dispatch parser"),
                    ),
                    patch(
                        "astrid.core.pack.install_local.validate_pack",
                        side_effect=AssertionError("canonical rollback used legacy validator"),
                    ),
                ):
                    result = rollback_pack(
                        "capability_only",
                        store=store,
                        revision=target_name,
                        skip_confirm=True,
                    )

                self.assertEqual(result, 1)
                self.assertEqual(_snapshot_tree(root / "packs"), before_store)
                self.assertEqual(
                    store.active_symlink_path("capability_only").readlink(),
                    before_active,
                )

    def test_canonical_rollback_rejects_hostile_targets_before_mutation_or_reads(
        self,
    ) -> None:
        cases = (
            "sibling-or-outside",
            "symlinked-target",
            "symlinked-manifest",
            "missing-manifest",
            "alternate-only-manifest",
            "mismatched-record",
            "direct-active-target",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source_v1 = root / "source-v1" / "capability_only"
                source_v2 = root / "source-v2" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source_v1)
                _copy_fixture_files(FIXTURES / "capability_only", source_v2)
                (source_v2 / "pack.yaml").write_text(
                    (source_v2 / "pack.yaml")
                    .read_text(encoding="utf-8")
                    .replace("version: 1.0.0", "version: 2.0.0"),
                    encoding="utf-8",
                )
                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(source_v1, **install_args), 0)
                self.assertEqual(
                    install_pack(source_v2, force=True, **install_args), 0
                )
                target_name = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                target_path = store.revisions_dir("capability_only") / target_name
                external_manifest = root / "outside-pack.yaml"
                external_manifest.write_text(
                    (target_path / "pack.yaml").read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                external_target = root / "outside-target"

                if case == "sibling-or-outside":
                    requested_revision = "../outside-target"
                elif case == "symlinked-target":
                    external_target.mkdir()
                    shutil.rmtree(target_path)
                    target_path.symlink_to(external_target, target_is_directory=True)
                    requested_revision = target_name
                elif case == "symlinked-manifest":
                    (target_path / "pack.yaml").unlink()
                    (target_path / "pack.yaml").symlink_to(external_manifest)
                    requested_revision = target_name
                elif case == "missing-manifest":
                    (target_path / "pack.yaml").unlink()
                    requested_revision = target_name
                elif case == "alternate-only-manifest":
                    (target_path / "pack.yaml").rename(target_path / "pack.yml")
                    requested_revision = target_name
                elif case == "mismatched-record":
                    record_path = target_path / ".astrid" / "install.json"
                    record_data = json.loads(record_path.read_text(encoding="utf-8"))
                    record_data["pack_id"] = "other_pack"
                    record_path.write_text(json.dumps(record_data), encoding="utf-8")
                    requested_revision = target_name
                else:
                    requested_revision = "capability_only"

                before_store = _snapshot_tree(store.install_root_for("capability_only"))
                before_external = (
                    _snapshot_tree(external_target)
                    if external_target.exists()
                    else None
                )
                read_paths: list[Path] = []
                original_read_text = Path.read_text
                original_stat = Path.stat

                def guarded_read_text(
                    path: Path, *args: object, **kwargs: object
                ) -> str:
                    read_paths.append(path)
                    if path.resolve() == external_manifest.resolve():
                        raise AssertionError("external rollback manifest was read")
                    return original_read_text(path, *args, **kwargs)

                def guarded_stat(
                    path: Path, *args: object, **kwargs: object
                ) -> os.stat_result:
                    if (
                        case == "symlinked-target"
                        and path == target_path
                        and kwargs.get("follow_symlinks", True)
                    ):
                        raise AssertionError("symlinked rollback target was stat'ed")
                    return original_stat(path, *args, **kwargs)

                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    patch.object(
                        Path, "read_text", autospec=True, side_effect=guarded_read_text
                    ),
                    patch.object(Path, "stat", autospec=True, side_effect=guarded_stat),
                ):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                        stderr
                    ):
                        try:
                            result = rollback_pack(
                                "capability_only",
                                store=store,
                                revision=requested_revision,
                                skip_confirm=True,
                            )
                        except AstridError as exc:
                            result = 1
                            raised = exc
                        else:
                            raised = None

                self.assertEqual(result, 1)
                if raised is not None:
                    self.assertEqual(raised.code, "pack.active_corrupt")
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(
                    _snapshot_tree(store.install_root_for("capability_only")),
                    before_store,
                )
                if before_external is not None:
                    self.assertEqual(_snapshot_tree(external_target), before_external)
                self.assertNotIn(
                    external_manifest.resolve(),
                    {path.resolve() for path in read_paths},
                )

    def test_rollback_rejects_forged_active_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_v1 = root / "source-v1" / "capability_only"
            source_v2 = root / "source-v2" / "capability_only"
            _copy_fixture_files(FIXTURES / "capability_only", source_v1)
            _copy_fixture_files(FIXTURES / "capability_only", source_v2)
            manifest = source_v2 / "pack.yaml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "version: 1.0.0", "version: 2.0.0"
                ),
                encoding="utf-8",
            )
            store = InstalledPackStore(packs_home=root / "packs")
            install_args = {
                "store": store,
                "skip_confirm": True,
                "trust_acknowledged": True,
            }
            self.assertEqual(install_pack(source_v1, **install_args), 0)
            self.assertEqual(install_pack(source_v2, force=True, **install_args), 0)

            target_name = next(
                path.name
                for path in store.list_revisions("capability_only")
                if path.name != "capability_only"
            )
            target_record_path = (
                store.revisions_dir("capability_only")
                / target_name
                / ".astrid"
                / "install.json"
            )
            target_record = json.loads(target_record_path.read_text(encoding="utf-8"))
            target_record["active"] = True
            target_record_path.write_text(
                json.dumps(target_record, indent=2), encoding="utf-8"
            )
            current_record_path = (
                store.active_revision_path("capability_only")
                / ".astrid"
                / "install.json"
            )
            staging = store.staging_path_for("capability_only")
            staging.mkdir(parents=True)
            (staging / "leftover.tmp").write_text("staging", encoding="utf-8")
            external = root / "external-sentinel"
            external.mkdir()
            (external / "sentinel.txt").write_text("untouched", encoding="utf-8")
            temp_path = root / "rollback-temp"
            temp_path.write_text("untouched", encoding="utf-8")
            before = {
                "active": store.active_symlink_path("capability_only").readlink(),
                "current_record": current_record_path.read_bytes(),
                "target_record": target_record_path.read_bytes(),
                "revisions": sorted(
                    path.name
                    for path in store.revisions_dir("capability_only").iterdir()
                ),
                "staging": (staging / "leftover.tmp").read_bytes(),
                "external": (external / "sentinel.txt").read_bytes(),
                "temp": temp_path.read_bytes(),
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with self.assertRaises(AstridError) as raised:
                    rollback_pack(
                        "capability_only",
                        store=store,
                        revision=target_name,
                        skip_confirm=True,
                    )
            self.assertEqual(raised.exception.code, "pack.active_corrupt")
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                store.active_symlink_path("capability_only").readlink(),
                before["active"],
            )
            self.assertEqual(target_record_path.read_bytes(), before["target_record"])
            self.assertEqual(
                sorted(
                    path.name
                    for path in store.revisions_dir("capability_only").iterdir()
                ),
                before["revisions"],
            )

            self.assertEqual(current_record_path.read_bytes(), before["current_record"])
            self.assertEqual((staging / "leftover.tmp").read_bytes(), before["staging"])
            self.assertEqual((external / "sentinel.txt").read_bytes(), before["external"])
            self.assertEqual(temp_path.read_bytes(), before["temp"])
    def test_installed_discovery_rejects_paired_legacy_discriminators(self) -> None:
        for discriminator in (1, 1.0):
            with self.subTest(discriminator=discriminator), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                store_home = root / "installed-home"
                store = InstalledPackStore(packs_home=store_home / "packs")
                self.assertEqual(
                    install_pack(
                        source,
                        store=store,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    ),
                    0,
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                record_path = active / ".astrid" / "install.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["schema_version"] = discriminator
                record["trust_summary"]["schema_version"] = discriminator
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
                with patch.dict(
                    os.environ,
                    {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                    clear=False,
                ):
                    with self.assertRaises(CanonicalPackValidationError):
                        discover_canonical_pack_metadata(include_installed=True)

    def test_installed_custody_binds_canonical_manifest_identity_and_bytes(self) -> None:
        mutations = {
            "version": ("version: 1.0.0", "version: 2.0.0"),
            "name": ("name: Capability Only", "name: Forged Name"),
            "id": ("id: capability_only", "id: forged"),
            "capabilities": ("capabilities: [render]", "capabilities: [different]"),
            "bytes": ("", "\n# byte drift\n"),
        }
        for label, (old, new) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "source" / "capability_only"
                _copy_fixture_files(FIXTURES / "capability_only", source)
                store_home = root / "installed-home"
                store = InstalledPackStore(packs_home=store_home / "packs")
                self.assertEqual(
                    install_pack(
                        source,
                        store=store,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    ),
                    0,
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                manifest = active / "pack.yaml"
                if label == "bytes":
                    manifest.write_text(manifest.read_text(encoding="utf-8") + new, encoding="utf-8")
                else:
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(old, new),
                        encoding="utf-8",
                    )
                before_pointer = store.active_symlink_path("capability_only").readlink()
                with patch.dict(
                    os.environ,
                    {"ASTRID_HOME": str(store_home), ASTRID_PACKS_PATH_ENV: ""},
                    clear=False,
                ):
                    with self.assertRaises(CanonicalPackValidationError):
                        discover_canonical_pack_metadata(include_installed=True)
                with self.assertRaises(AstridError):
                    update_pack(
                        "capability_only",
                        store=store,
                        dry_run=True,
                        skip_confirm=True,
                        trust_acknowledged=True,
                    )
                self.assertEqual(
                    store.active_symlink_path("capability_only").readlink(),
                    before_pointer,
                )

    def test_rollback_rejects_missing_alternate_and_drifted_canonical_custody(self) -> None:
        for manifest_mode in ("missing", "alternate", "target_drift"):
            with self.subTest(manifest_mode=manifest_mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sources: dict[str, Path] = {}
                for version in ("1.0.0", "2.0.0"):
                    source = root / f"source-{version}" / "capability_only"
                    _copy_fixture_files(FIXTURES / "capability_only", source)
                    manifest = source / "pack.yaml"
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8").replace(
                            "version: 1.0.0", f"version: {version}"
                        ),
                        encoding="utf-8",
                    )
                    sources[version] = source
                store = InstalledPackStore(packs_home=root / "packs")
                install_args = {
                    "store": store,
                    "skip_confirm": True,
                    "trust_acknowledged": True,
                }
                self.assertEqual(install_pack(sources["1.0.0"], **install_args), 0)
                self.assertEqual(
                    install_pack(sources["2.0.0"], force=True, **install_args),
                    0,
                )
                target_name = next(
                    path.name
                    for path in store.list_revisions("capability_only")
                    if path.name != "capability_only"
                )
                active = store.active_revision_path("capability_only")
                self.assertIsNotNone(active)
                assert active is not None
                target = store.revisions_dir("capability_only") / target_name
                if manifest_mode == "missing":
                    (active / "pack.yaml").unlink()
                elif manifest_mode == "alternate":
                    (active / "pack.yaml").rename(active / "pack.yml")
                else:
                    target_manifest = target / "pack.yaml"
                    target_manifest.write_text(
                        target_manifest.read_text(encoding="utf-8") + "\n# drift\n",
                        encoding="utf-8",
                    )
                before_pointer = store.active_symlink_path("capability_only").readlink()
                if manifest_mode == "target_drift":
                    self.assertEqual(
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_name,
                            skip_confirm=True,
                        ),
                        1,
                    )
                else:
                    with self.assertRaises(AstridError):
                        rollback_pack(
                            "capability_only",
                            store=store,
                            revision=target_name,
                            skip_confirm=True,
                        )
                self.assertEqual(
                    store.active_symlink_path("capability_only").readlink(),
                    before_pointer,
                )
if __name__ == "__main__":
    unittest.main()
