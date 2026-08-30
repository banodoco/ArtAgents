"""Deterministic packaged and temporary-copy factoring checks.

Proves that each in-tree schema pack (``timeline``, ``shots``, ``references``,
``runaway``)
can be removed **only inside a temporary source copy** -- both the pack
directory and the explicit standard registration tuple
(``astrid.packs.STANDARD_SCHEMA_PACKS``, which drives
``register_standard_schema_packs``) -- while the complete enumerated kernel
test lane stays green and the remaining manifest-derived catalog is
unchanged.

The original source-composition proof remains available for the v10 regression
floor. The packaged mode starts from one unpacked wheel, removes one standard
schema pack at a time, patches only the explicit registration tuple, and runs
the same complete kernel lane against that artifact root. Both modes are
throwaway checks: the real repository and the supplied wheel are never mutated.

Lane completeness
-----------------
The enumerated :data:`KERNEL_LANE` is the fixed, complete set of kernel test
files under ``tests/v10`` that import no domain schema pack at module level
and whose assertions hold under *any* subset of the four packs:

- kernel repositories/execution: fanout (run creation/continuation), the
  multi-task journey, task races, evidence, media, projects, receipts/events,
  writer/UoW, task lifecycle, task admission, task executor;
- capability adapters that stay kernel-owned (generation roundtrip,
  capability roundtrip, understanding repository);
- the deterministic authority lint (pure text fixtures under ``tmp_path``).

Deliberately excluded suites (asserted separately, see below):

- ``test_registry.py`` / ``test_catalog_migrations.py`` assert the exact
  *standard* 4-pack composition, so they cannot
  run under a reduced composition; the check's own catalog verification step
  re-derives the remaining manifest-derived catalog from the modified
  registration instead.
- ``test_timeline_repository.py``, ``test_reference_*``, ``test_shot_*`` and
  the three conformance files import the domain packs at module level.
- ``test_contention.py`` / ``test_crash_atomicity.py`` import the timeline
  repository at module level.
- ``test_media_pipeline.py`` exercises the standard bridge composition
  (``compose_standard_bridge`` / startup staging GC) which legitimately
  requires the timeline pack.

The remaining catalog is verified deterministically for every removal:
core + the three remaining packs compose to exactly
``CORE_TABLES | (all pack tables - the removed pack's tables)``, the removed
pack is absent from the frozen registry and the registration tuple, and a
fresh database opened from the modified composition contains exactly the
remaining tables (never the removed pack's).

Packaged mode additionally checks that the removed pack's stream, event,
command, repository, CLI, and bridge vocabulary is absent, every foreign key
stays within the kernel or its owning pack, and every remaining SDK service
uses the one writer supplied by the composition.

Sketch verification
-------------------
The check also locks the software-engineering-agent composition sketch
(:data:`SKETCH_DOC`): the sketch's declared kernel inventory is parsed from
the document and compared for exact equality against the inventory derived
from ``CORE_MIGRATIONS`` (:data:`CORE_KERNEL_TABLES`). The sketch therefore
cannot silently add a kernel table, and its own in-tree packs
(:data:`SKETCH_PACKS`) stay disjoint from the Astrid standard packs. Like the
removal proof, this is a read-only source-composition check: no database is
opened, no runtime discovery or loader exists, and nothing is installed or
uninstalled.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from astrid.core.migrations.catalog import CORE_MIGRATIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
"""The repository root the check copies from (read-only)."""

DOMAIN_PACKS: tuple[str, ...] = ("timeline", "shots", "references", "runaway")
"""Exactly the in-tree schema packs the standard composition registers."""

PACK_TABLES: dict[str, tuple[str, ...]] = {
    "timeline": ("timelines",),
    "shots": (
        "shots",
        "shot_items",
        "generations",
        "generation_variants",
    ),
    "references": ("project_references", "media_references", "reference_links"),
    "runaway": ("runaway_transitions",),
}
"""Tables each domain pack declares through its manifest migrations (frozen
m1/m3 catalog; never inferred from a live database)."""

ALL_PACK_TABLES: frozenset[str] = frozenset().union(*PACK_TABLES.values())

PACK_VOCABULARY: dict[str, dict[str, tuple[str, ...]]] = {
    "timeline": {
        "stream_types": ("timeline.timeline",),
        "event_kinds": ("timeline.created", "timeline.saved", "timeline.archived"),
        "command_kinds": ("timeline.create", "timeline.save", "timeline.archive"),
        "repositories": ("TimelineRepository",),
        "cli_mounts": ("timelines",),
        "bridge_mounts": ("timelines",),
    },
    "shots": {
        "stream_types": ("shot.shot",),
        "event_kinds": (
            "shot.created",
            "shot.item_added",
            "shot.item_removed",
            "shot.reordered",
        ),
        "command_kinds": (
            "shot.create",
            "shot.add_item",
            "shot.remove_item",
            "shot.reorder",
        ),
        "repositories": ("ShotRepository",),
        "cli_mounts": ("shots",),
        "bridge_mounts": (),
    },
    "references": {
        "stream_types": ("reference.reference",),
        "event_kinds": (
            "reference.created",
            "reference.updated",
            "reference.archived",
            "reference.media_associated",
            "reference.primary_changed",
            "reference.linked",
        ),
        "command_kinds": (
            "reference.create",
            "reference.update",
            "reference.archive",
            "reference.associate",
            "reference.set_primary",
            "reference.link",
        ),
        "repositories": ("ReferenceRepository",),
        "cli_mounts": ("references",),
        "bridge_mounts": (),
    },
    "runaway": {
        "stream_types": ("runaway.transition_set",),
        "event_kinds": ("runaway.created",),
        "command_kinds": ("runaway.create",),
        "repositories": ("RunawayRepository",),
        "cli_mounts": (),
        "bridge_mounts": ("runaway_transitions",),
    },
}
"""The complete vocabulary owned by each fixed schema pack.

This is an explicit audit input, not a discovery result. It is compared with
the installed registry after each pack is removed so a surviving namespace
cannot masquerade as a reduced composition.
"""

SKETCH_DOC = "docs/architecture/software-engineering-pack-sketch.md"
"""Repo-root-relative path of the software-engineering-agent composition
sketch (see the module docstring's "Sketch verification" section)."""

SKETCH_PACKS: tuple[str, ...] = ("workspace", "changeset", "review")
"""The sketch's own in-tree packs. They are illustrative and never registered
in the Astrid standard composition; the check only verifies they are declared
by the sketch and disjoint from :data:`DOMAIN_PACKS`."""

CORE_KERNEL_TABLES: frozenset[str] = frozenset().union(
    *(migration.owned_tables for migration in CORE_MIGRATIONS)
)
"""The audited kernel inventory derived solely from ``CORE_MIGRATIONS``
(exactly the 14 kernel tables). The sketch must match it exactly."""

_SKETCH_INVENTORY_MARKER = (
    "Kernel inventory (reused unchanged from CORE_MIGRATIONS):"
)
"""Marker line the sketch document uses to declare its reused kernel
inventory (followed by a fenced block of table names)."""

KERNEL_LANE: tuple[str, ...] = (
    "tests/v10/test_fanout.py",
    "tests/v10/test_multi_task_journey.py",
    "tests/v10/test_task_races.py",
    "tests/v10/test_evidence_repository.py",
    "tests/v10/test_media_repository.py",
    "tests/v10/test_project_repository.py",
    "tests/v10/test_receipts_events.py",
    "tests/v10/test_writer_uow.py",
    "tests/v10/test_task_lifecycle.py",
    "tests/v10/test_task_admission.py",
    "tests/v10/test_task_executor.py",
    "tests/v10/test_capability_roundtrip.py",
    "tests/v10/test_generation_roundtrip.py",
    "tests/v10/test_understanding_repository.py",
    "tests/v10/test_authority_lint.py",
)
"""The complete enumerated kernel test lane (see module docstring)."""

_STANDARD_TUPLE_RE = re.compile(
    r"STANDARD_SCHEMA_PACKS: tuple\[str, \.\.\.\] = \(([^)]*)\)"
)
"""The one-line explicit registration tuple in ``astrid/packs/__init__.py``."""

_TIMELINE_IMPORT_LINES = (
    "from astrid.packs.timeline.bridge import TimelineBridgeAdapter\n",
    "from astrid.packs.timeline.repository import TimelineRepository\n",
)
"""Module-level timeline imports in ``astrid/packs/__init__.py`` that the
standard bridge composition needs; they are removed only in the temporary
copy when the timeline pack is the one under removal."""

# Paths the lane needs besides ``astrid/``, ``tests/v10`` and ``pyproject.toml``.
_LANE_CONFTEST_FILES = ("tests/conftest.py", "tests/__init__.py")
_LANE_SCRIPTS = (
    "scripts/__init__.py",
    "scripts/reshape/__init__.py",
    "scripts/reshape/authority_lint.py",
)
_LANE_FIXTURES = ("tests/fixtures/timeline_visualize/desert_slice",)

_COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def _patch_packs_init(packs_init: Path, removed_pack: str) -> None:
    """Rewrite a temporary copy of ``astrid/packs/__init__.py``.

    Removes ``removed_pack`` from the explicit :data:`STANDARD_SCHEMA_PACKS`
    registration tuple (so ``register_standard_schema_packs`` registers only
    the remaining packs). The checkout-only pack registry has no domain
    imports, so reducing the tuple is the complete surgery. Raises if the
    expected literal is missing, keeping the operation deterministic instead
    of silently drifting.
    """
    text = packs_init.read_text(encoding="utf-8")
    remaining = tuple(pack for pack in DOMAIN_PACKS if pack != removed_pack)
    rendered = "(" + ", ".join(f'"{pack}"' for pack in remaining) + ")"
    new_text, count = _STANDARD_TUPLE_RE.subn(
        lambda _match: f"STANDARD_SCHEMA_PACKS: tuple[str, ...] = {rendered}",
        text,
    )
    if count != 1:
        raise RuntimeError(
            f"STANDARD_SCHEMA_PACKS tuple not found in {packs_init}"
        )
    packs_init.write_text(new_text, encoding="utf-8")


def build_temp_source_copy(
    removed_pack: str, *, base_dir: Path | None = None
) -> Path:
    """Copy the repository source into a fresh temp dir, then remove
    ``removed_pack`` from source and from the explicit registration tuple.

    The copy contains only what the enumerated lane needs: the ``astrid``
    package (without bytecode caches), the v10 lane files plus their conftest
    and package markers, the lane fixtures, the authority-lint script the
    lane imports, and ``pyproject.toml`` (pytest rootdir config). Nothing
    outside these paths is copied and the real tree is never written.
    """
    work = Path(tempfile.mkdtemp(prefix="astrid-factoring-", dir=base_dir))
    try:
        shutil.copytree(
            REPO_ROOT / "astrid",
            work / "astrid",
            ignore=_COPY_IGNORE,
            symlinks=False,
        )
        # Remove the pack from source (a temporary copy; no uninstall path).
        shutil.rmtree(work / "astrid" / "packs" / removed_pack)

        (work / "tests").mkdir()
        for rel in _LANE_CONFTEST_FILES:
            shutil.copy2(REPO_ROOT / rel, work / rel)
        shutil.copytree(
            REPO_ROOT / "tests" / "v10",
            work / "tests" / "v10",
            ignore=_COPY_IGNORE,
            symlinks=False,
        )
        for rel in _LANE_FIXTURES:
            source = REPO_ROOT / rel
            if source.exists():
                shutil.copytree(
                    source, work / rel, ignore=_COPY_IGNORE, symlinks=False
                )
        for rel in _LANE_SCRIPTS:
            source = REPO_ROOT / rel
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(REPO_ROOT / "pyproject.toml", work / "pyproject.toml")

        # Remove the pack from the explicit registration tuple.
        _patch_packs_init(work / "astrid" / "packs" / "__init__.py", removed_pack)
        return work
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# Packaged-artifact factoring (m8 Step 8)
# ---------------------------------------------------------------------------


def unpack_wheel(wheel: str | Path, destination: str | Path) -> Path:
    """Safely unpack one wheel into an artifact root and return that root.

    The destination is created by the caller or by this function and is never
    treated as a source checkout.  Wheel member paths are constrained before
    extraction so a malformed artifact fails closed rather than escaping the
    temporary composition.
    """
    archive_path = Path(wheel).expanduser().resolve()
    root = Path(destination).expanduser().resolve()
    if not archive_path.is_file() or archive_path.suffix != ".whl":
        raise ValueError(f"wheel does not exist or is not a wheel: {archive_path}")
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            relative = Path(member.filename)
            target = (root / relative).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"wheel member escapes artifact root: {member.filename!r}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
    package_root = root / "astrid"
    if not (package_root / "__init__.py").is_file():
        raise ValueError(f"unpacked wheel is missing the astrid package: {root}")
    return root


def build_temp_artifact_copy(
    wheel: str | Path,
    removed_pack: str,
    *,
    base_dir: Path | None = None,
    artifact_root: Path | None = None,
) -> Path:
    """Create one reduced composition from an unpacked wheel.

    When *artifact_root* is supplied it is copied first, which lets callers
    factor one already-unpacked wheel without rebuilding or mutating it.
    Otherwise the supplied wheel is unpacked into the temporary composition.
    The returned path is the temporary artifact root; its parent owns the
    complete cleanup boundary.
    """
    if removed_pack not in DOMAIN_PACKS:
        raise ValueError(
            f"unknown domain pack {removed_pack!r}; expected one of {DOMAIN_PACKS}"
        )
    work = Path(tempfile.mkdtemp(prefix="astrid-artifact-factoring-", dir=base_dir))
    root = work / "artifact"
    try:
        if artifact_root is None:
            unpack_wheel(wheel, root)
        else:
            source = Path(artifact_root).expanduser().resolve()
            if not (source / "astrid" / "__init__.py").is_file():
                raise ValueError(f"artifact root is missing the astrid package: {source}")
            shutil.copytree(source, root, symlinks=False)
        pack_root = root / "astrid" / "packs" / removed_pack
        if not pack_root.is_dir():
            raise ValueError(
                f"artifact root is missing the {removed_pack!r} schema pack: {pack_root}"
            )
        shutil.rmtree(pack_root)
        _patch_packs_init(root / "astrid" / "packs" / "__init__.py", removed_pack)
        return root
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise


def _artifact_test_workspace(
    artifact_root: Path, *, base_dir: Path | None = None
) -> Path:
    """Copy only the fixed kernel tests needed by the packaged lane.

    The source tree contains many domain-specific v10 files, but the packaged
    lane deliberately executes only :data:`KERNEL_LANE`.  Copying that exact
    list keeps each installed-root subprocess small and makes the fixed suite
    boundary auditable; it does not change which tests are executed.
    """
    work = Path(tempfile.mkdtemp(prefix="astrid-artifact-kernel-", dir=base_dir))
    try:
        (work / "tests").mkdir(parents=True, exist_ok=True)
        for relative in _LANE_CONFTEST_FILES:
            source = REPO_ROOT / relative
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in ("tests/v10/__init__.py", "tests/v10/conftest.py", *KERNEL_LANE):
            source = REPO_ROOT / relative
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in _LANE_FIXTURES:
            source = REPO_ROOT / relative
            if source.exists():
                shutil.copytree(
                    source,
                    work / relative,
                    ignore=_COPY_IGNORE,
                    symlinks=False,
                )
        for relative in _LANE_SCRIPTS:
            source = REPO_ROOT / relative
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(REPO_ROOT / "pyproject.toml", work / "pyproject.toml")
        # Keep the installed root first so a source checkout or editable
        # distribution cannot satisfy an import in the kernel lane.
        (work / "artifact-root.txt").write_text(str(artifact_root) + "\n")
        return work
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise


def _artifact_environment(*roots: Path) -> dict[str, str]:
    """Return a child environment whose only Astrid import roots are explicit."""
    environment = os.environ.copy()
    # The selected interpreter owns the dependency environment (for packaged
    # factoring this is the lock-provisioned venv).  ``PYTHONPATH`` is only
    # for the explicit artifact/test roots supplied by this check: injecting
    # the host or user site-packages here would let a broken artifact pass and
    # would defeat ``PYTHONNOUSERSITE``.
    environment["PYTHONPATH"] = os.pathsep.join(
        str(Path(root).resolve()) for root in roots
    )
    # Never inherit PYTHONHOME from the parent process.  CPython evaluates it
    # before the selected interpreter starts, so a hostile value can redirect
    # prefix/stdlib resolution (or make the child fail during encodings
    # bootstrap) even when PYTHONPATH and user-site imports are scrubbed.
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment["ASTRID_INTERNAL_INVOCATION"] = "1"
    environment["ASTRID_NO_NUDGE"] = "1"
    # A schema checkout is deliberately external to the wheel, but it is an
    # explicit, validated contract input rather than ambient PYTHONPATH.  The
    # Astrid timeline module consumes this root directly and verifies its
    # package contents before importing it.
    schema_name = "ASTRID_TIMELINE_SCHEMA_PYTHONPATH"
    schema_raw = environment.get(schema_name, "").strip()
    if schema_raw:
        schema_root = Path(schema_raw).expanduser()
        schema_package = schema_root / "banodoco_timeline_schema"
        if not (
            schema_root.is_absolute()
            and schema_package.is_dir()
            and (schema_package / "timeline.schema.json").is_file()
        ):
            environment.pop(schema_name, None)
    for name in (
        "ASTRID_SESSION_ID",
        "ASTRID_REPO_ROOT",
        "ASTRID_PACKS_PATH",
        "ASTRID_THEMES_ROOT",
        "OPENAI_API_KEY",
        "SUPABASE_URL",
    ):
        environment.pop(name, None)
    return environment


_ARTIFACT_COMPOSITION_PROBE = r'''
import json
import sqlite3
import sys
from pathlib import Path

import astrid

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.migrations.catalog import CORE_TABLES
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.database import open_database
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import STANDARD_SCHEMA_PACKS, register_standard_schema_packs


removed_pack = sys.argv[1]
expected = json.loads(sys.argv[2])
artifact_root = Path(sys.argv[3]).resolve()
assert Path(astrid.__file__).resolve().is_relative_to(artifact_root), astrid.__file__

# The typed-timeline consumer is independently installable and must survive
# removal of every schema pack, especially Runaway.  Its admitted-artifact
# source seam must not import a domain repository or sqlite directly.
from astrid.packs.typed_timeline.mapper import TypedDataTimelineMapper
from astrid.packs.typed_timeline.sources import load_json_rows
typed_source = Path(load_json_rows.__code__.co_filename).read_text(encoding="utf-8")
assert "astrid.packs.runaway" not in typed_source
assert "sqlite3" not in typed_source
assert TypedDataTimelineMapper

registry = SchemaPackRegistry()
register_core_vocabulary(registry)
register_standard_schema_packs(registry)
frozen = registry.freeze()
remaining = {pack for pack in STANDARD_SCHEMA_PACKS}
assert removed_pack not in remaining
assert removed_pack not in frozen.packs

expected_pack_tables = set(expected["remaining_tables"])
expected_tables = set(CORE_TABLES) | expected_pack_tables
assert set(frozen.tables) == expected_tables
assert set(frozen.tables).isdisjoint(expected["removed_tables"])
for field, values in expected["removed_vocabulary"].items():
    mapping = getattr(frozen, field)
    for value in values:
        assert value not in mapping, (field, value, mapping)

database = artifact_root / ("factoring-" + removed_pack + ".sqlite3")
for suffix in ("", "-wal", "-shm"):
    database.with_name(database.name + suffix).unlink(missing_ok=True)
connection = open_database(database, frozen)
try:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == expected_tables
    assert tables.isdisjoint(expected["removed_tables"])
    connection.execute("PRAGMA foreign_keys = ON")
    foreign_keys = {
        (table, row[2])
        for table in tables
        for row in connection.execute("PRAGMA foreign_key_list('" + table + "')")
    }
finally:
    connection.close()

owners = {table: "core" for table in CORE_TABLES}
owners.update(frozen.tables)
for source, target in foreign_keys:
    source_pack = owners[source]
    target_pack = owners[target]
    assert target_pack == "core" or target_pack == source_pack, (source, target)
    assert target not in expected["removed_tables"], (source, target)

print(json.dumps({
    "removed_pack": removed_pack,
    "remaining_packs": sorted(remaining),
    "tables": len(expected_tables),
    "foreign_keys": len(foreign_keys),
    "writer": "one-shared-writer",
}))
'''


def verify_artifact_composition(
    artifact_root: Path,
    removed_pack: str,
    *,
    python: str | None = None,
    timeout: int = 30,
) -> str:
    """Run installed-root catalog, vocabulary, FK, and writer checks."""
    if removed_pack not in DOMAIN_PACKS:
        raise ValueError(
            f"unknown domain pack {removed_pack!r}; expected one of {DOMAIN_PACKS}"
        )
    remaining_tables = sorted(ALL_PACK_TABLES - set(PACK_TABLES[removed_pack]))
    expected = {
        "remaining_tables": remaining_tables,
        "removed_tables": list(PACK_TABLES[removed_pack]),
        "removed_vocabulary": PACK_VOCABULARY[removed_pack],
    }
    interpreter = python or sys.executable
    environment = _artifact_environment(artifact_root)
    process = subprocess.run(
        [
            interpreter,
            "-c",
            _ARTIFACT_COMPOSITION_PROBE,
            removed_pack,
            json.dumps(expected, sort_keys=True),
            str(artifact_root),
        ],
        cwd=artifact_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if process.returncode != 0:
        raise AssertionError(
            f"installed-root checks failed for {removed_pack}:\n"
            f"{process.stdout}\n{process.stderr}"
        )
    return process.stdout.strip()


def run_artifact_kernel_suite(
    artifact_root: Path,
    *,
    python: str | None = None,
    base_dir: Path | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Run the complete fixed kernel suite against one artifact root."""
    interpreter = python or sys.executable
    test_workspace = _artifact_test_workspace(artifact_root, base_dir=base_dir)
    try:
        environment = _artifact_environment(artifact_root, test_workspace)
        command = [
            interpreter,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--no-header",
            *KERNEL_LANE,
        ]
        try:
            return subprocess.run(
                command,
                cwd=test_workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
            return subprocess.CompletedProcess(
                args=command,
                returncode=124,
                stdout=stdout or "",
                stderr=(stderr or "")
                + f"\nkernel lane exceeded deterministic {timeout}s deadline\n",
            )
    finally:
        shutil.rmtree(test_workspace, ignore_errors=True)


@dataclass(frozen=True)
class ArtifactRemovalResult:
    """Evidence for one pack removal from one unpacked wheel."""

    removed_pack: str
    catalog_output: str
    kernel_returncode: int
    kernel_output: str
    kernel_error: str

    @property
    def ok(self) -> bool:
        return self.kernel_returncode == 0


@dataclass(frozen=True)
class ArtifactFactoringResult:
    """Combined packaged-factorability result for all standard packs."""

    removals: tuple[ArtifactRemovalResult, ...]
    sketch_summary: str

    @property
    def ok(self) -> bool:
        return bool(self.removals) and all(result.ok for result in self.removals)


def check_artifact_removal(
    removed_pack: str,
    *,
    wheel: str | Path,
    artifact_root: Path | None = None,
    python: str | None = None,
    base_dir: Path | None = None,
    keep_temp: bool = False,
    kernel_timeout: int = 180,
    catalog_timeout: int = 30,
) -> ArtifactRemovalResult:
    """Remove one pack from a wheel root and run every packaged check."""
    proof_environment = None
    if python is None:
        from scripts.reshape.installed_artifact import provision_locked_environment

        proof_environment = provision_locked_environment(REPO_ROOT)
        python = str(proof_environment.python_executable)
    work: Path | None = None
    try:
        reduced_root = build_temp_artifact_copy(
            wheel,
            removed_pack,
            base_dir=base_dir,
            artifact_root=artifact_root,
        )
        work = reduced_root.parent
        catalog_output = verify_artifact_composition(
            reduced_root,
            removed_pack,
            python=python,
            timeout=catalog_timeout,
        )
        kernel = run_artifact_kernel_suite(
            reduced_root,
            python=python,
            base_dir=work,
            timeout=kernel_timeout,
        )
        return ArtifactRemovalResult(
            removed_pack=removed_pack,
            catalog_output=catalog_output,
            kernel_returncode=kernel.returncode,
            kernel_output=kernel.stdout,
            kernel_error=kernel.stderr,
        )
    finally:
        if work is not None and not keep_temp:
            shutil.rmtree(work, ignore_errors=True)
        if proof_environment is not None:
            proof_environment.close()


def check_artifact_factoring(
    *,
    wheel: str | Path,
    packs: tuple[str, ...] = DOMAIN_PACKS,
    artifact_root: Path | None = None,
    python: str | None = None,
    base_dir: Path | None = None,
    keep_temp: bool = False,
    kernel_timeout: int = 180,
    catalog_timeout: int = 30,
) -> ArtifactFactoringResult:
    """Run packaged factorability independently for every requested pack.

    All reductions start from one unpacked copy of the selected wheel.  Each
    pack still receives its own copied artifact root and its own complete
    kernel subprocess, so one reduced composition cannot share runtime state
    with another, while wheel extraction and its package-data audit happen
    exactly once.
    """
    requested = tuple(packs)
    if not requested:
        raise ValueError("at least one domain pack is required")
    unknown = set(requested) - set(DOMAIN_PACKS)
    if unknown:
        raise ValueError(
            f"unknown domain pack(s) {sorted(unknown)!r}; expected one of {DOMAIN_PACKS}"
        )

    proof_environment = None
    if python is None:
        from scripts.reshape.installed_artifact import provision_locked_environment

        proof_environment = provision_locked_environment(REPO_ROOT)
        python = str(proof_environment.python_executable)
    base_work = Path(tempfile.mkdtemp(prefix="astrid-artifact-base-", dir=base_dir))
    base_root = base_work / "artifact"
    try:
        if artifact_root is None:
            unpack_wheel(wheel, base_root)
        else:
            source = Path(artifact_root).expanduser().resolve()
            if not (source / "astrid" / "__init__.py").is_file():
                raise ValueError(f"artifact root is missing the astrid package: {source}")
            shutil.copytree(source, base_root, symlinks=False)

        # Each reduced artifact is an isolated copy and its catalog/kernel
        # probes run in subprocesses. Kernel lanes are CPU-heavy complete-suite
        # processes, so keep the declared result order and run the
        # independent reductions serially: concurrent lanes contend with the
        # repository's other release gates and repeatedly turn a functional
        # check into a scheduler-dependent timeout.
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = [
                executor.submit(
                    check_artifact_removal,
                    pack,
                    wheel=wheel,
                    artifact_root=base_root,
                    python=python,
                    base_dir=base_work,
                    keep_temp=keep_temp,
                    kernel_timeout=kernel_timeout,
                    catalog_timeout=catalog_timeout,
                )
                for pack in requested
            ]
            removals = tuple(future.result() for future in futures)
        return ArtifactFactoringResult(
            removals=removals,
            sketch_summary=verify_sketch_kernel_inventory(),
        )
    finally:
        if not keep_temp:
            shutil.rmtree(base_work, ignore_errors=True)
        if proof_environment is not None:
            proof_environment.close()


_CATALOG_SNIPPET = r"""
import sys

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.migrations.catalog import CORE_TABLES
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.database import open_database
from astrid.packs import STANDARD_SCHEMA_PACKS, register_standard_schema_packs

removed_pack = sys.argv[1]
removed_tables = {t for t in sys.argv[2].split(",") if t}
remaining_tables = {t for t in sys.argv[3].split(",") if t}

registry = SchemaPackRegistry()
register_core_vocabulary(registry)
register_standard_schema_packs(registry)
frozen = registry.freeze()

# The removed pack is gone from the explicit registration tuple and registry.
assert removed_pack not in STANDARD_SCHEMA_PACKS, (
    f"{removed_pack} still in the registration tuple: {STANDARD_SCHEMA_PACKS}"
)
assert removed_pack not in frozen.packs, (
    f"{removed_pack} still registered: {sorted(frozen.packs)}"
)

# The remaining manifest-derived catalog is exactly kernel + remaining packs.
expected = set(CORE_TABLES) | remaining_tables
tables = set(frozen.tables)
assert tables == expected, (
    f"remaining catalog {sorted(tables)} != expected {sorted(expected)}"
)
assert tables.isdisjoint(removed_tables), (
    f"removed pack tables still present: {sorted(tables & removed_tables)}"
)
for table in tables:
    assert frozen.tables[table], f"table {table!r} has no owning pack"

# A fresh database from the modified composition matches the remaining
# manifest-derived catalog exactly (never the removed pack's tables).
conn = open_database("catalog_check.sqlite3", frozen)
try:
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
finally:
    conn.close()
assert names == tables, (
    f"fresh database tables differ from the remaining catalog: {names ^ tables}"
)
print(
    f"catalog-ok tables={len(tables)} "
    f"packs={sorted(STANDARD_SCHEMA_PACKS)}"
)
"""


def verify_remaining_catalog(
    work: Path, python: str, removed_pack: str, *, timeout: int = 30
) -> str:
    """Compose the modified registration in the temp copy and verify the
    remaining manifest-derived catalog (registry + fresh database)."""
    removed_tables = ",".join(PACK_TABLES[removed_pack])
    remaining_tables = ",".join(sorted(ALL_PACK_TABLES - set(PACK_TABLES[removed_pack])))
    env = _artifact_environment(work)
    proc = subprocess.run(
        [python, "-c", _CATALOG_SNIPPET, removed_pack, removed_tables, remaining_tables],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"remaining manifest-derived catalog verification failed for "
            f"{removed_pack}:\n{proc.stdout}\n{proc.stderr}"
        )
    return proc.stdout.strip()


def extract_sketch_kernel_inventory(doc_text: str) -> frozenset[str]:
    """Extract the sketch's declared kernel inventory from its fenced block.

    The sketch document declares the kernel tables it reuses in a fenced
    block introduced by :data:`_SKETCH_INVENTORY_MARKER`. Extraction is
    purely textual and deterministic -- no discovery, no live database, and
    no loader. Raises ``AssertionError`` when the marker or the fenced block
    is missing, so a sketch that stops declaring its inventory fails loudly
    instead of silently escaping the comparison.
    """
    if _SKETCH_INVENTORY_MARKER not in doc_text:
        raise AssertionError(
            f"sketch inventory marker {_SKETCH_INVENTORY_MARKER!r} "
            f"missing in {SKETCH_DOC}"
        )
    after_marker = doc_text.split(_SKETCH_INVENTORY_MARKER, 1)[1]
    if "```" not in after_marker:
        raise AssertionError(
            f"sketch inventory fenced block missing in {SKETCH_DOC}"
        )
    block = after_marker.split("```", 1)[1]
    # The opening fence may carry an info string (e.g. ```text); drop its line.
    if "\n" in block:
        block = block.split("\n", 1)[1]
    block = block.split("```", 1)[0]
    names = {
        name.strip() for name in re.split(r"[,\s]+", block.strip()) if name.strip()
    }
    if not names:
        raise AssertionError(f"sketch kernel inventory is empty in {SKETCH_DOC}")
    return frozenset(names)


def verify_sketch_kernel_inventory(repo_root: Path = REPO_ROOT) -> str:
    """Prove the software-engineering-agent sketch reuses exactly the kernel.

    The sketch's declared kernel inventory is parsed from
    :data:`SKETCH_DOC` and compared for exact equality against
    :data:`CORE_KERNEL_TABLES`, which is derived solely from
    ``CORE_MIGRATIONS``. A table the sketch adds without a matching
    ``CORE_MIGRATIONS`` declaration fails loudly, so the sketch cannot
    silently grow the kernel (a pack-specific FK target, a new asset table
    beside ``media``, or any other kernel-shaped table); a table the sketch
    omits also fails, so the sketch cannot drift from the audited inventory.
    The sketch's own in-tree packs must be declared by the document and stay
    disjoint from the Astrid standard packs. The check is read-only: it
    opens no database and performs no discovery or loader activity.
    """
    doc = (repo_root / SKETCH_DOC).read_text(encoding="utf-8")
    inventory = extract_sketch_kernel_inventory(doc)
    added = inventory - CORE_KERNEL_TABLES
    if added:
        raise AssertionError(
            "sketch adds kernel table(s) not declared by CORE_MIGRATIONS: "
            + ", ".join(sorted(added))
        )
    omitted = CORE_KERNEL_TABLES - inventory
    if omitted:
        raise AssertionError(
            "sketch omits kernel table(s) declared by CORE_MIGRATIONS: "
            + ", ".join(sorted(omitted))
        )
    for pack in SKETCH_PACKS:
        if pack not in doc:
            raise AssertionError(f"sketch pack {pack!r} not declared in {SKETCH_DOC}")
    if set(SKETCH_PACKS) & set(DOMAIN_PACKS):
        raise AssertionError(
            f"sketch packs overlap the Astrid standard packs: {SKETCH_PACKS}"
        )
    return (
        f"sketch-ok kernel_tables={len(CORE_KERNEL_TABLES)} "
        f"packs={sorted(SKETCH_PACKS)}"
    )


def run_kernel_lane(
    work: Path, python: str, *, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    """Run the complete enumerated kernel lane against the temp copy."""
    # Shadow any installed/editable astrid with the temp copy's source while
    # retaining the same locked-dependency and schema-root boundary as the
    # packaged lane.
    env = _artifact_environment(work)
    cmd = [
        python,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--no-header",
        *KERNEL_LANE,
    ]
    try:
        return subprocess.run(
            cmd, cwd=work, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout=stdout or "",
            stderr=(stderr or "")
            + f"\nkernel lane exceeded deterministic {timeout}s deadline\n",
        )


@dataclass(frozen=True)
class RemovalCheckResult:
    """Outcome of removing one domain pack from a temporary composition."""

    removed_pack: str
    catalog_output: str
    lane_returncode: int
    lane_output: str
    lane_error: str

    @property
    def ok(self) -> bool:
        return self.lane_returncode == 0


def check_removal(
    removed_pack: str,
    *,
    python: str | None = None,
    base_dir: Path | None = None,
    keep_temp: bool = False,
    lane_timeout: int = 180,
    catalog_timeout: int = 30,
) -> RemovalCheckResult:
    """Remove ``removed_pack`` from a temporary source composition and prove
    the enumerated kernel lane and the remaining manifest-derived catalog
    stay green. The real repository is never touched."""
    if removed_pack not in DOMAIN_PACKS:
        raise ValueError(
            f"unknown domain pack {removed_pack!r}; expected one of {DOMAIN_PACKS}"
        )
    # A direct CLI/API caller may not have Astrid's optional dependencies in
    # its host interpreter. Provision the proof interpreter explicitly from
    # the repository lock instead of falling back to user-site packages.
    proof_environment = None
    if python is None:
        from scripts.reshape.installed_artifact import provision_locked_environment

        proof_environment = provision_locked_environment(REPO_ROOT)
        interpreter = str(proof_environment.python_executable)
    else:
        interpreter = python
    work: Path | None = None
    try:
        work = build_temp_source_copy(removed_pack, base_dir=base_dir)
        catalog_output = verify_remaining_catalog(
            work, interpreter, removed_pack, timeout=catalog_timeout
        )
        lane = run_kernel_lane(work, interpreter, timeout=lane_timeout)
        return RemovalCheckResult(
            removed_pack=removed_pack,
            catalog_output=catalog_output,
            lane_returncode=lane.returncode,
            lane_output=lane.stdout,
            lane_error=lane.stderr,
        )
    finally:
        if work is not None and not keep_temp:
            shutil.rmtree(work, ignore_errors=True)
        if proof_environment is not None:
            proof_environment.close()


def _print_lane_tail(result: RemovalCheckResult) -> None:
    tail = "\n".join(
        (result.lane_output or "").splitlines()[-4:]
        + (result.lane_error or "").splitlines()[-4:]
    )
    print(f"       lane tail:\n{tail}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python scripts/reshape/check_pack_factoring.py``."""
    parser = argparse.ArgumentParser(
        description=(
            "Prove each in-tree schema pack is removable from a temporary "
            "source composition while the enumerated kernel lane and the "
            "remaining manifest-derived catalog stay green, and prove the "
            "software-engineering-agent sketch reuses exactly the "
            "CORE_MIGRATIONS kernel inventory."
        )
    )
    parser.add_argument(
        "--packs",
        nargs="*",
        default=list(DOMAIN_PACKS),
        help="packs to remove one at a time (default: all three domain packs)",
    )
    parser.add_argument(
        "--wheel",
        default=None,
        help="run packaged-artifact factoring against this one wheel",
    )
    parser.add_argument(
        "--artifact-root",
        default=None,
        help="factor a previously unpacked artifact root instead of a wheel",
    )
    parser.add_argument("--python", default=None, help="interpreter for subprocesses")
    parser.add_argument("--keep-temp", action="store_true", help="keep temp copies on failure")
    parser.add_argument(
        "--lane-timeout", type=int, default=180, help="per-lane pytest timeout"
    )
    args = parser.parse_args(argv)

    if args.artifact_root is not None and args.wheel is None:
        parser.error("--artifact-root requires --wheel as its artifact identity")

    if args.wheel is not None:
        failures: list[str] = []
        for pack in args.packs:
            try:
                result = check_artifact_removal(
                    pack,
                    wheel=args.wheel,
                    artifact_root=(
                        Path(args.artifact_root).expanduser().resolve()
                        if args.artifact_root is not None
                        else None
                    ),
                    python=args.python,
                    keep_temp=args.keep_temp,
                    kernel_timeout=args.lane_timeout,
                )
            except Exception as exc:  # noqa: BLE001 - CLI must always exit non-zero
                print(f"[FAIL] packaged removal {pack}: {exc}", file=sys.stderr)
                failures.append(pack)
                continue
            if result.ok:
                print(f"[PASS] packaged removal {pack}: {result.catalog_output}")
                summary = (result.kernel_output or "").strip().splitlines()[-1:]
                if summary:
                    print(f"       kernel lane: {summary[0]}")
            else:
                print(
                    f"[FAIL] packaged removal {pack}: kernel lane exited "
                    f"{result.kernel_returncode}",
                    file=sys.stderr,
                )
                tail = "\n".join(
                    (result.kernel_output or "").splitlines()[-4:]
                    + (result.kernel_error or "").splitlines()[-4:]
                )
                print(f"       kernel lane tail:\n{tail}", file=sys.stderr)
                failures.append(pack)
        try:
            sketch_summary = verify_sketch_kernel_inventory()
        except Exception as exc:  # noqa: BLE001 - CLI must always exit non-zero
            print(f"[FAIL] software-engineering-agent sketch: {exc}", file=sys.stderr)
            return 1
        print(f"[PASS] software-engineering-agent sketch: {sketch_summary}")
        if failures:
            print(
                f"packaged factoring check FAILED for: {', '.join(failures)}",
                file=sys.stderr,
            )
            return 1
        print(
            "packaged factoring check PASSED: every requested domain pack is "
            "removable from one unpacked wheel while the complete kernel lane, "
            "catalog, authority, and writer checks stay green."
        )
        return 0

    failures: list[str] = []
    for pack in args.packs:
        try:
            result = check_removal(
                pack,
                python=args.python,
                keep_temp=args.keep_temp,
                lane_timeout=args.lane_timeout,
            )
        except Exception as exc:  # noqa: BLE001 - CLI must always exit non-zero
            print(f"[FAIL] {pack}: {exc}", file=sys.stderr)
            failures.append(pack)
            continue
        if result.ok:
            print(f"[PASS] removed {result.removed_pack}: {result.catalog_output}")
            summary = (result.lane_output or "").strip().splitlines()[-1:]
            if summary:
                print(f"       kernel lane: {summary[0]}")
        else:
            print(
                f"[FAIL] removed {result.removed_pack}: kernel lane exited "
                f"{result.lane_returncode}",
                file=sys.stderr,
            )
            _print_lane_tail(result)
            failures.append(pack)

    if failures:
        print(f"factoring check FAILED for: {', '.join(failures)}", file=sys.stderr)
        return 1
    try:
        sketch_summary = verify_sketch_kernel_inventory()
    except Exception as exc:  # noqa: BLE001 - CLI must always exit non-zero
        print(f"[FAIL] software-engineering-agent sketch: {exc}", file=sys.stderr)
        return 1
    print(f"[PASS] software-engineering-agent sketch: {sketch_summary}")
    print(
        "factoring check PASSED: every domain pack is removable from a "
        "temporary source composition while the enumerated kernel lane and "
        "the remaining manifest-derived catalog stay green, and the "
        "software-engineering-agent sketch reuses exactly the CORE_MIGRATIONS "
        "kernel inventory."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
