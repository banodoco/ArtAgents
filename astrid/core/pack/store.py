"""Installed-pack store: records, paths, symlinks, locks, and root discovery.

Layout under ``~/.astrid/packs/`` (honours ``ASTRID_HOME``)::

    <pack_id>/
      active -> revisions/<pack_id>/          # symlink to active revision
      revisions/
        <pack_id>/                             # active revision directory
          .astrid/
            install.json                       # InstallRecord as JSON
        <pack_id>.<timestamp>/                 # rotated-out old revisions
      staging/                                 # temporary staging area
      .astrid/
        install.lock                           # filelock mutex

The revision directory is named after *pack_id* so that ``PackResolver``
satisfies ``root.name == pack_id`` (an invariant enforced during pack
manifest loading).
"""

from __future__ import annotations

import hashlib
import os
import stat
import json as _json
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from astrid.core.pack._common import SymlinkedPackPathError, reject_symlinked_path

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.canonical import (
    CanonicalPackEntry,
    CanonicalPackValidationError,
    ExternalPackSource,
    canonical_manifest_path,
    read_normalize_validate,
)
from astrid.core.session.paths import installed_packs_root
from astrid.core.util.log_and_swallow import log_and_swallow
try:
    from filelock import FileLock as _FileLock
except ImportError:  # pragma: no cover — dev-friendly fallback
    _FileLock = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Install record
# ---------------------------------------------------------------------------


@dataclass
class InstallRecord:
    """Per-revision install metadata written to ``.astrid/install.json``."""

    pack_id: str
    name: str
    version: str
    schema_version: int | str
    source_path: str
    installed_at: str  # ISO-8601 UTC
    revision: str  # revision directory name, e.g. "<pack_id>" or "<pack_id>.<ts>"
    install_root: str  # absolute path of the per-pack root (<packs root>/<pack_id>)
    active: bool = True

    # Extended fields (populated when available)
    manifest_digest: str = ""
    component_inventory: dict[str, int] = field(default_factory=dict)
    entrypoints: list[str] = field(default_factory=list)
    declared_secrets: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    trust_summary: dict = field(default_factory=dict)

    # Git-backed and trust fields (all defaulted for backward compat)
    source_type: str = "local"  # "local" or "git"
    git_url: str = ""  # durable Git URL (not temp checkout path)
    commit_sha: str = ""  # pinned commit SHA (40 hex chars)
    requested_ref: str = ""  # branch/tag requested at install time
    astrid_version: str = ""  # from pack manifest data.get('astrid_version', '')
    trust_tier: str = ""  # "local" or "git"
    last_validation_time: str = ""  # ISO-8601 UTC of last validation
    previous_active_revision: str = ""  # revision dir name replaced during force-install
    trust_acknowledged_at: str = ""  # ISO-8601 UTC when trust was accepted
    trust_method: str = ""  # "interactive", "cli_flag", "api", or "test"
    trust_actor: str = ""  # "cli", "api", "test", or another caller label
    no_sandbox_warning_version: int | None = None
    permissions_accepted: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "InstallRecord":
        # Filter to known fields to stay forward-compatible
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


def _is_canonical_v2_record(record: InstallRecord) -> bool:
    """Return whether an installed record is owned by canonical v2."""
    return type(record.schema_version) is int and record.schema_version == 2


def _manifest_path_for_installed_record(
    record: InstallRecord,
    pack_root: Path,
) -> Path | None:
    """Select the confined canonical manifest for an installed revision."""
    if not _is_canonical_v2_record(record):
        raise CanonicalPackValidationError(
            f"installed record for pack {record.pack_id!r} is not canonical v2"
        )
    if not pack_root.is_absolute() or pack_root.name != record.revision:
        raise CanonicalPackValidationError(
            f"canonical pack source identity is not confined to {record.pack_id!r}: "
            f"{pack_root}"
        )
    try:
        confined_root = reject_symlinked_path(pack_root)
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"canonical pack source must not be a symlink or contain "
            f"symlinked ancestors: {pack_root}"
        ) from exc
    if not confined_root.is_dir():
        return None
    return canonical_manifest_path(confined_root)


def _validate_canonical_record_custody_metadata(
    store: "InstalledPackStore",
    record: InstallRecord,
) -> None:
    """Require the metadata that binds a canonical revision to its bytes."""
    if not isinstance(record.manifest_digest, str) or not record.manifest_digest.strip():
        raise store._active_corrupt(
            f"canonical install record for pack {record.pack_id!r} "
            "is missing manifest digest custody"
        )
    if not isinstance(record.trust_summary, dict) or not record.trust_summary:
        raise store._active_corrupt(
            f"canonical install record for pack {record.pack_id!r} "
            "is missing trust-summary custody"
        )


def _validate_canonical_record_identity(
    store: "InstalledPackStore",
    record: InstallRecord,
    entry: CanonicalPackEntry,
    *,
    propagate_canonical_errors: bool = False,
) -> None:
    expected = {
        "pack_id": entry.definition.id,
        "name": entry.definition.name,
        "version": entry.definition.version,
        "schema_version": entry.definition.schema_version,
    }
    actual = {
        "pack_id": record.pack_id,
        "name": record.name,
        "version": record.version,
        "schema_version": record.schema_version,
    }

    def mismatch() -> None:
        if propagate_canonical_errors:
            raise CanonicalPackValidationError(
                f"installed canonical metadata for pack {record.pack_id!r} "
                "does not match its manifest"
            )
        raise store._active_corrupt(
            f"installed canonical metadata for pack {record.pack_id!r} "
            "does not match its manifest"
        )

    if actual != expected:
        mismatch()
    summary = record.trust_summary
    if summary is not None and not isinstance(summary, dict):
        raise store._active_corrupt(
            f"installed canonical trust metadata for pack {record.pack_id!r} "
            "is malformed"
        )
    if isinstance(summary, dict):
        for key, value in expected.items():
            if key in summary and summary[key] != value:
                mismatch()


def _validate_installed_manifest_digest(
    store: "InstalledPackStore",
    record: InstallRecord,
    manifest_path: Path,
    *,
    canonical: bool,
) -> None:
    if _is_canonical_v2_record(record):
        _validate_canonical_record_custody_metadata(store, record)
    if not record.manifest_digest:
        return
    if not isinstance(record.manifest_digest, str):
        raise store._active_corrupt(
            f"installed manifest digest for pack {record.pack_id!r} is malformed"
        )
    try:
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise store._active_corrupt(
            f"installed manifest for pack {record.pack_id!r} is unreadable"
        ) from exc
    if digest == record.manifest_digest:
        return
    if canonical:
        raise CanonicalPackValidationError(
            f"installed manifest for pack {record.pack_id!r} "
            "does not match its recorded digest"
        )
    raise store._active_corrupt(
        f"installed manifest for pack {record.pack_id!r} "
        "does not match its recorded digest"
    )

def validate_installed_manifest_custody(
    store: "InstalledPackStore",
    record: InstallRecord,
    pack_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
    propagate_canonical_errors: bool = False,
    read_validate_fn=None,
) -> CanonicalPackEntry:
    """Bind a canonical installed record to its manifest and custody."""
    if not _is_canonical_v2_record(record):
        raise store._active_corrupt(
            f"installed record for pack {record.pack_id!r} is not canonical v2"
        )
    if pack_root is None:
        pack_root = store.active_revision_path(record.pack_id)
    if pack_root is None:
        raise store._active_corrupt(
            f"active revision for pack {record.pack_id!r} is unavailable"
        )
    _validate_canonical_record_custody_metadata(store, record)
    if manifest_path is None:
        try:
            manifest_path = _manifest_path_for_installed_record(record, pack_root)
        except CanonicalPackValidationError as exc:
            raise store._active_corrupt(
                f"installed manifest custody for pack {record.pack_id!r} is invalid"
            ) from exc
    if manifest_path is None:
        raise store._active_corrupt(
            f"installed pack {record.pack_id!r} has no canonical pack.yaml"
        )
    try:
        entry = (read_validate_fn or read_normalize_validate)(
            manifest_path,
            source=ExternalPackSource.INSTALLED,
            resolve_resources=True,
            expected_pack_id=record.pack_id,
        )
        _validate_canonical_record_identity(
            store,
            record,
            entry,
            propagate_canonical_errors=propagate_canonical_errors,
        )
        _validate_installed_manifest_digest(
            store,
            record,
            manifest_path,
            canonical=propagate_canonical_errors,
        )
        return entry
    except Exception as exc:
        if propagate_canonical_errors and isinstance(
            exc, CanonicalPackValidationError
        ):
            raise
        if isinstance(exc, AstridError):
            raise
        raise store._active_corrupt(
            f"installed canonical manifest for pack {record.pack_id!r} "
            "failed strict validation"
        ) from exc



class _PackStateSnapshot:
    """Temporary copy of the mutable publication state for one pack."""

    _EXCLUDED_ROOT_ENTRIES = frozenset({".astrid"})

    def __init__(self, root: Path) -> None:
        self.root = root
        self._backup = Path(tempfile.mkdtemp(prefix="astrid_pack_state_"))
        if root.is_dir() and not root.is_symlink():
            for child in root.iterdir():
                if child.name in self._EXCLUDED_ROOT_ENTRIES:
                    continue
                destination = self._backup / child.name
                if child.is_symlink():
                    os.symlink(child.readlink(), destination)
                elif child.is_dir():
                    shutil.copytree(child, destination, symlinks=True)
                else:
                    shutil.copy2(child, destination, follow_symlinks=False)

    @classmethod
    def capture(cls, root: Path) -> "_PackStateSnapshot":
        return cls(root)

    @staticmethod
    def _remove(path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            path.unlink(missing_ok=True)
        else:
            shutil.rmtree(path)

    def restore(self) -> None:
        """Restore every mutable root entry exactly as captured."""
        if self.root.is_symlink() or not self.root.is_dir():
            self.root.unlink(missing_ok=True)
            self.root.mkdir(parents=True, exist_ok=True)
        else:
            for child in self.root.iterdir():
                if child.name not in self._EXCLUDED_ROOT_ENTRIES:
                    self._remove(child)
        for child in self._backup.iterdir():
            destination = self.root / child.name
            if child.is_symlink():
                os.symlink(child.readlink(), destination)
            elif child.is_dir():
                shutil.copytree(child, destination, symlinks=True)
            else:
                shutil.copy2(child, destination, follow_symlinks=False)

    def cleanup(self) -> None:
        shutil.rmtree(self._backup, ignore_errors=True)

# ---------------------------------------------------------------------------
# InstalledPackStore
# ---------------------------------------------------------------------------


class InstalledPackStore:
    """Manage installed packs under the per-user packs home.

    The *packs_home* parameter (defaults to ``installed_packs_root()``)
    exists so tests can use temporary directories.  It is captured as an
    absolute lexical path so relative install records remain cwd-independent;
    symlink components remain visible to custody validation.
    """

    def __init__(self, packs_home: str | Path | None = None) -> None:
        home = Path(packs_home) if packs_home else installed_packs_root()
        # Make relative records stable across later cwd changes without
        # resolving symlinked custody boundaries away.
        self._home = Path(os.path.abspath(home.expanduser()))

    def _snapshot_pack_state(self, pack_id: str) -> _PackStateSnapshot:
        """Capture mutable publication entries before a lifecycle mutation."""
        return _PackStateSnapshot.capture(self.install_root_for(pack_id))

    # -- path helpers --------------------------------------------------------

    def install_root_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>``."""
        return self._home / pack_id

    def active_symlink_path(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/active`` (the symlink)."""
        return self.install_root_for(pack_id) / "active"

    def revisions_dir(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/revisions``."""
        return self.install_root_for(pack_id) / "revisions"
    @staticmethod
    def validate_revision_name(revision_dir_name: str | Path) -> str:
        """Validate a revision identifier before filesystem resolution."""
        if not isinstance(revision_dir_name, (str, Path)):
            raise AstridError(
                f"Revision {revision_dir_name!r} must be a single directory name",
                code="pack.active_corrupt",
            )
        name = str(revision_dir_name)
        if (
            not name
            or name in {".", ".."}
            or "/" in name
            or "\\" in name
            or "\x00" in name
            or Path(name).is_absolute()
        ):
            raise AstridError(
                f"Revision {revision_dir_name!r} must be a single directory name "
                "inside the pack's revisions/ directory",
                code="pack.active_corrupt",
            )
        return name


    def active_revision_path(self, pack_id: str) -> Path | None:
        """Resolve the active symlink to a confined direct revision directory.

        Returns ``None`` when the symlink does not exist, is broken, points
        through a symlinked/escaped revision root, or targets a nested path.
        Active install-record validation belongs to callers that admit roots.
        """
        try:
            install_root = reject_symlinked_path(self.install_root_for(pack_id))
            revisions_root = reject_symlinked_path(install_root / "revisions")
        except SymlinkedPackPathError:
            return None
        link = install_root / "active"
        if not link.is_symlink():
            return None
        try:
            target = link.readlink()
        except OSError:
            return None
        if target.is_absolute():
            return None
        target_path = link.parent / target
        try:
            relative_target = target_path.relative_to(revisions_root)
        except ValueError:
            return None
        if len(relative_target.parts) != 1:
            return None
        if not relative_target.parts or ".." in relative_target.parts:
            return None
        try:
            reject_symlinked_path(target_path)
            revisions_resolved = revisions_root.resolve(strict=False)
            resolved = target_path.resolve(strict=False)
        except (OSError, SymlinkedPackPathError):
            return None
        if not resolved.is_relative_to(revisions_resolved):
            return None
        if not resolved.is_dir():
            return None
        return resolved

    def staging_path_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/staging``."""
        return self.install_root_for(pack_id) / "staging"

    def lock_path_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/.astrid/install.lock``."""
        return self.install_root_for(pack_id) / ".astrid" / "install.lock"

    # -- locking -------------------------------------------------------------

    def _acquire_lock(self, pack_id: str, timeout: float = 30.0):
        """Acquire a filelock for *pack_id*.  Returns a context-manager.

        If *filelock* is not available, returns a no-op context manager and
        emits a warning.
        """
        if _FileLock is None:
            import warnings
            warnings.warn(
                "filelock not installed; concurrent install protection disabled"
            )
            return _NoOpLock()

        lock_path = self.lock_path_for(pack_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        return _FileLock(str(lock_path), timeout=timeout)

    # -- listing / querying --------------------------------------------------

    def list_installed(self) -> list[InstallRecord]:
        """Return all installed pack records, newest-first.

        When ``~/.astrid/packs/`` does not exist, returns an empty list.
        """
        if not self._home.is_dir():
            return []
        records: list[InstallRecord] = []
        try:
            for child in sorted(self._home.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                rec = self._read_active_record(child.name)
                if rec is not None:
                    records.append(rec)
        except OSError:
            return []
        # Sort newest-first by installed_at
        records.sort(key=lambda r: r.installed_at, reverse=True)
        return records

    def get_active(self, pack_id: str) -> InstallRecord | None:
        """Return the active InstallRecord for *pack_id*, or ``None``."""
        return self._read_active_record(pack_id)

    def is_installed(self, pack_id: str) -> bool:
        """Return ``True`` when *pack_id* has an active install."""
        return self.get_active(pack_id) is not None
    def get_active_strict(self, pack_id: str) -> InstallRecord | None:
        """Read active custody, distinguishing absence from corruption.

        Read-only discovery intentionally uses :meth:`get_active`, which is
        tolerant.  Mutating lifecycle commands use this strict variant so an
        existing but malformed install cannot be treated as absent.
        """
        install_root = self.install_root_for(pack_id)
        if not install_root.exists() and not install_root.is_symlink():
            return None
        root = self._strict_directory(
            install_root, f"install root for pack {pack_id!r}"
        )
        revisions = root / "revisions"
        if not revisions.exists() and not revisions.is_symlink():
            return None
        revisions_root = self._strict_directory(
            revisions, f"revisions root for pack {pack_id!r}"
        )
        link = root / "active"
        if not link.exists() and not link.is_symlink():
            return None
        if not link.is_symlink():
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} is not a symlink"
            )
        target_path = self._strict_active_target(
            root, revisions_root, link, pack_id
        )
        record = self._validate_install_record(
            pack_id, target_path, expected_active=True
        )
        if _is_canonical_v2_record(record):
            _validate_canonical_record_custody_metadata(self, record)
        return record

    def _active_corrupt(self, message: str) -> AstridError:
        return AstridError(
            f"active state is corrupt: {message}",
            code="pack.active_corrupt",
            recovery_command="inspect the pack's active pointer and install records",
        )

    @staticmethod
    def _strict_directory(path: Path, description: str) -> Path:
        try:
            candidate = reject_symlinked_path(path)
        except SymlinkedPackPathError as exc:
            raise AstridError(
                f"{description} contains a symlink: {path}",
                code="pack.active_corrupt",
            ) from exc
        if not candidate.is_dir():
            raise AstridError(
                f"{description} is not a directory: {path}",
                code="pack.active_corrupt",
            )
        return candidate
    def _strict_active_target(
        self,
        install_root: Path,
        revisions_root: Path,
        link: Path,
        pack_id: str,
    ) -> Path:
        try:
            target = link.readlink()
        except OSError as exc:
            raise self._active_corrupt(
                f"cannot read active pointer for pack {pack_id!r}"
            ) from exc
        if target.is_absolute():
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} must be relative"
            )
        target_path = link.parent / target
        try:
            relative_target = target_path.relative_to(revisions_root)
        except ValueError as exc:
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} escapes revisions/"
            ) from exc
        if (
            not relative_target.parts
            or ".." in relative_target.parts
            or len(relative_target.parts) != 1
        ):
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} must target one revision"
            )
        try:
            reject_symlinked_path(target_path)
            revisions_resolved = revisions_root.resolve(strict=False)
            resolved = target_path.resolve(strict=False)
        except (OSError, SymlinkedPackPathError) as exc:
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} is not confined"
            ) from exc
        if not resolved.is_relative_to(revisions_resolved) or not resolved.is_dir():
            raise self._active_corrupt(
                f"active pointer for pack {pack_id!r} targets an invalid revision"
            )
        return resolved

    @staticmethod
    def _validate_record_schema_metadata(
        data: dict,
        pack_id: str,
    ) -> None:
        """Require exact canonical v2 discriminators and agreement."""
        schema_version = data["schema_version"]
        summary = data.get("trust_summary")
        if summary is not None and not isinstance(summary, dict):
            raise TypeError("trust_summary must be an object")
        summary_present = isinstance(summary, dict) and bool(summary)
        summary_version = summary.get("schema_version") if summary_present else None
        if type(schema_version) is not int or schema_version != 2:
            raise TypeError(
                f"schema_version for pack {pack_id!r} must be exactly integer 2"
            )
        if summary_present and (
            type(summary_version) is not int or summary_version != 2
        ):
            raise TypeError(
                f"trust_summary schema_version for pack {pack_id!r} must be exactly integer 2"
            )

    def _validate_install_record(
        self,
        pack_id: str,
        revision_root: Path,
        *,
        expected_active: bool | None = None,
    ) -> InstallRecord:
        """Validate install metadata before a lifecycle mutation."""
        try:
            revision_root = reject_symlinked_path(revision_root)
            revisions_root = reject_symlinked_path(self.revisions_dir(pack_id))
        except SymlinkedPackPathError as exc:
            raise self._active_corrupt(
                f"revision custody for pack {pack_id!r} is symlinked"
            ) from exc
        if not revision_root.is_dir():
            raise self._active_corrupt(
                f"revision {revision_root.name!r} for pack {pack_id!r} is not a directory"
            )
        try:
            if revision_root.parent != revisions_root:
                raise ValueError("revision is outside revisions/")
        except (OSError, ValueError) as exc:
            raise self._active_corrupt(
                f"revision {revision_root.name!r} for pack {pack_id!r} is not confined"
            ) from exc
        metadata_root = revision_root / ".astrid"
        record_path = metadata_root / "install.json"
        if (
            metadata_root.is_symlink()
            or record_path.is_symlink()
            or not metadata_root.is_dir()
            or not record_path.is_file()
        ):
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} is missing or not confined"
            )
        try:
            data = _json.loads(record_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("record must be an object")
            required_record_keys = {
                "pack_id",
                "name",
                "version",
                "schema_version",
                "source_path",
                "installed_at",
                "revision",
                "install_root",
                "active",
            }
            if not required_record_keys.issubset(data):
                raise TypeError("record is missing required custody fields")
            self._validate_record_schema_metadata(data, pack_id)
            record = InstallRecord.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} is malformed"
            ) from exc
        required_strings = (
            ("pack_id", record.pack_id),
            ("name", record.name),
            ("version", record.version),
            ("source_path", record.source_path),
            ("installed_at", record.installed_at),
            ("revision", record.revision),
            ("install_root", record.install_root),
        )
        if any(
            not isinstance(value, str) or not value.strip()
            for _, value in required_strings
        ):
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} has invalid required fields"
            )
        if record.pack_id != pack_id or record.revision != revision_root.name:
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} has invalid identity or revision"
            )
        expected_root = self.install_root_for(pack_id)
        try:
            if (
                not Path(record.install_root).is_absolute()
                or Path(record.install_root).resolve(strict=False)
                != expected_root.resolve(strict=False)
            ):
                raise ValueError("install root mismatch")
        except (OSError, ValueError) as exc:
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} has invalid install root"
            ) from exc
        if type(record.active) is not bool:
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} has invalid active state"
            )
        if expected_active is not None and record.active is not expected_active:
            raise self._active_corrupt(
                f"install record for pack {pack_id!r} has unexpected active state"
            )
        return record

    def assert_rollback_custody(
        self, pack_id: str, revision_dir_name: str
    ) -> tuple[InstallRecord, InstallRecord]:
        """Validate current and inactive target records before rollback."""
        revision_dir_name = self.validate_revision_name(revision_dir_name)
        current = self.get_active_strict(pack_id)
        if current is None:
            raise self._active_corrupt(f"pack {pack_id!r} has no active revision")
        revisions_root = self.assert_revisions_root(pack_id)
        target_path = revisions_root / revision_dir_name
        try:
            reject_symlinked_path(target_path)
        except SymlinkedPackPathError as exc:
            raise self._active_corrupt(
                f"rollback target {revision_dir_name!r} is symlinked"
            ) from exc
        if not target_path.is_dir():
            raise self._active_corrupt(
                f"rollback target {revision_dir_name!r} for pack {pack_id!r} does not exist"
            )
        target = self._validate_install_record(
            pack_id, target_path, expected_active=False
        )
        if _is_canonical_v2_record(target):
            _validate_canonical_record_custody_metadata(self, target)
        return current, target


    # -- active pack roots ---------------------------------------------------

    def assert_revisions_root(self, pack_id: str) -> Path:
        """Return a safe existing revisions root without creating anything."""
        install_root = self.install_root_for(pack_id)
        try:
            root = reject_symlinked_path(install_root)
        except SymlinkedPackPathError as exc:
            raise AstridError(
                f"installed pack root for {pack_id!r} contains a symlink",
                code="pack.active_corrupt",
            ) from exc
        if root.exists() and not root.is_dir():
            raise AstridError(
                f"installed pack root for {pack_id!r} is not a directory",
                code="pack.active_corrupt",
            )
        revisions = root / "revisions"
        try:
            revisions = reject_symlinked_path(revisions)
        except SymlinkedPackPathError as exc:
            raise AstridError(
                f"revisions root for pack {pack_id!r} must not be a symlink",
                code="pack.active_corrupt",
            ) from exc
        if revisions.exists() and not revisions.is_dir():
            raise AstridError(
                f"revisions root for pack {pack_id!r} is not a directory",
                code="pack.active_corrupt",
            )
        return revisions

    def assert_install_target(self, pack_id: str) -> Path | None:
        """Validate a pre-existing direct revision before installation.

        The canonical install path may replace ``revisions/<pack_id>``.
        Validate its complete custody before any install-record read or
        publication operation so a hostile target cannot redirect writes.
        """
        revisions_root = self.assert_revisions_root(pack_id)
        target_path = revisions_root / self.validate_revision_name(pack_id)
        try:
            target_stat = target_path.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise self._active_corrupt(
                f"installation target for pack {pack_id!r} cannot be inspected"
            ) from exc
        if stat.S_ISLNK(target_stat.st_mode):
            raise self._active_corrupt(
                f"installation target for pack {pack_id!r} is symlinked"
            )
        if not stat.S_ISDIR(target_stat.st_mode):
            raise self._active_corrupt(
                f"installation target for pack {pack_id!r} is not a directory"
            )
        try:
            reject_symlinked_path(target_path)
            revisions_resolved = revisions_root.resolve(strict=False)
            target_resolved = target_path.resolve(strict=False)
        except (OSError, SymlinkedPackPathError) as exc:
            raise self._active_corrupt(
                f"installation target for pack {pack_id!r} is not confined"
            ) from exc
        if (
            target_resolved.parent != revisions_resolved
            or not target_resolved.is_dir()
        ):
            raise self._active_corrupt(
                f"installation target for pack {pack_id!r} is not confined"
            )
        self._validate_install_record(pack_id, target_path)
        return target_path


    def active_pack_roots(self) -> tuple[Path, ...]:
        """Return resolved, custody-validated revision directories.

        Each returned path is the real revision directory (not the ``active``
        symlink), satisfying ``PackResolver``'s ``root.name == pack_id``
        invariant.  Manifest form, strict canonical identity, and recorded
        manifest digests are validated before a root reaches discovery.

        Returns an empty tuple when ``~/.astrid/packs/`` does not exist.
        """
        try:
            home = reject_symlinked_path(self._home)
        except SymlinkedPackPathError:
            return ()
        if not home.is_dir():
            return ()
        roots: list[Path] = []
        try:
            for child in sorted(home.iterdir()):
                try:
                    child = reject_symlinked_path(child)
                except SymlinkedPackPathError:
                    continue
                rev = self.active_revision_path(child.name)
                if rev is None:
                    continue
                try:
                    record = self._validate_install_record(
                        child.name, rev, expected_active=True
                    )
                    if canonical_manifest_path(rev) is None:
                        continue
                    validate_installed_manifest_custody(
                        self,
                        record,
                        rev,
                        propagate_canonical_errors=True,
                    )
                except AstridError:
                    continue
                roots.append(rev)
        except OSError:
            return ()
        return tuple(roots)

    # -- mutations -----------------------------------------------------------

    def record_install(self, record: InstallRecord) -> None:
        """Persist *record* to ``<revision>/.astrid/install.json``."""
        rev_dir = Path(record.install_root) / "revisions" / record.revision
        astrid_dir = rev_dir / ".astrid"
        astrid_dir.mkdir(parents=True, exist_ok=True)
        record_path = astrid_dir / "install.json"
        record_path.write_text(
            _json.dumps(record.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def mark_inactive(self, pack_id: str) -> None:
        """Remove the *active* symlink so the pack is no longer discoverable."""
        link = self.active_symlink_path(pack_id)
        try:
            link.unlink(missing_ok=True)
        except OSError:
            pass

    def remove_install(self, pack_id: str, *, keep_revisions: bool = False) -> None:
        """Remove an installed pack completely (or keep revision dirs).

        Args:
            pack_id: The pack to remove.
            keep_revisions: If ``True``, leave the revisions directory intact.
        """
        root = self.install_root_for(pack_id)
        if not root.is_dir():
            return

        # Remove active symlink
        self.mark_inactive(pack_id)

        # Remove staging area if present
        staging = self.staging_path_for(pack_id)
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)

        # Remove lock file
        lock = self.lock_path_for(pack_id)
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass

        if keep_revisions:
            # Preserve revisions dir, just clean up the per-pack root metadata
            astrid_meta = root / ".astrid"
            if astrid_meta.is_dir():
                shutil.rmtree(astrid_meta, ignore_errors=True)
        else:
            shutil.rmtree(root, ignore_errors=True)

    # -- revision management --------------------------------------------------

    def list_revisions(self, pack_id: str) -> list[Path]:
        """Return all regular revision directories for *pack_id*, newest-first.

        Revision children are inspected with ``lstat`` so untrusted symlinks
        and non-directory entries cannot redirect metadata reads.

        Returns an empty list when no revisions exist (e.g. the pack has
        never been installed or the revisions directory was removed).
        """
        rev_dir = self.revisions_dir(pack_id)
        try:
            rev_dir = reject_symlinked_path(rev_dir)
            rev_stat = rev_dir.lstat()
        except (OSError, SymlinkedPackPathError):
            return []
        if not stat.S_ISDIR(rev_stat.st_mode):
            return []
        entries: list[tuple[Path, float]] = []
        try:
            for path in rev_dir.iterdir():
                try:
                    child_stat = path.lstat()
                except OSError:
                    continue
                if stat.S_ISDIR(child_stat.st_mode):
                    entries.append((path, child_stat.st_mtime))
        except OSError:
            return []
        entries.sort(key=lambda item: item[1], reverse=True)
        return [path for path, _mtime in entries]

    def _read_revision_record(
        self, pack_id: str, revision_dir_name: str
    ) -> InstallRecord | None:
        """Read the install.json from a specific revision directory.

        Unlike :meth:`_read_active_record`, this reads the record for
        *any* revision — active, inactive, or rotated-out — as long as
        its directory still exists under ``revisions/``.

        Returns ``None`` when the revision directory (or its
        ``.astrid/install.json``) is missing or unparseable.
        """
        rev_path = self.revisions_dir(pack_id) / revision_dir_name
        record_path = rev_path / ".astrid" / "install.json"
        if not record_path.is_file():
            return None
        try:
            data = _json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            return None
        try:
            return InstallRecord.from_dict(data)
        except (TypeError, Exception):
            return None

    def _mark_revision_inactive(
        self,
        pack_id: str,
        revision_dir_name: str,
        *,
        record: InstallRecord | None = None,
    ) -> None:
        """Write ``active=False`` into a revision's install.json.

        A caller that already admitted the record through strict custody may
        pass it directly.  This avoids rediscovering publication state after
        the active pointer has switched.
        """
        if record is None:
            record = self._read_revision_record(pack_id, revision_dir_name)
        if record is None:
            return
        record.active = False
        self._write_revision_record(pack_id, revision_dir_name, record)

    def _mark_revision_active(self, pack_id: str, revision_dir_name: str) -> None:
        """Write ``active=True`` into the revision's install.json."""
        record = self._read_revision_record(pack_id, revision_dir_name)
        if record is None:
            return
        record.active = True
        self._write_revision_record(pack_id, revision_dir_name, record)

    def _write_revision_record(
        self, pack_id: str, revision_dir_name: str, record: InstallRecord
    ) -> None:
        """Persist a record to the named on-disk revision."""
        rev_dir = self.revisions_dir(pack_id) / revision_dir_name
        astrid_dir = rev_dir / ".astrid"
        astrid_dir.mkdir(parents=True, exist_ok=True)
        (astrid_dir / "install.json").write_text(
            _json.dumps(record.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def rollback_to_revision(self, pack_id: str, revision_dir_name: str) -> None:
        """Activate an existing confined revision after custody validation."""
        revision_dir_name = self.validate_revision_name(revision_dir_name)
        revisions_root = self.assert_revisions_root(pack_id)
        target_path = revisions_root / revision_dir_name
        try:
            reject_symlinked_path(target_path)
        except SymlinkedPackPathError as exc:
            raise self._active_corrupt(
                f"rollback target {revision_dir_name!r} is symlinked"
            ) from exc
        if not target_path.is_dir():
            raise AstridError(
                f"Revision {revision_dir_name!r} does not exist for pack {pack_id!r}",
                recovery_command="list available revisions under the pack's revisions/ directory",
            )
        old_active = self.active_revision_path(pack_id)
        if old_active is not None and old_active.resolve(strict=False) == target_path.resolve(strict=False):
            return
        if old_active is not None:
            old_record = self._validate_install_record(
                pack_id, old_active, expected_active=True
            )
            validate_installed_manifest_custody(self, old_record, old_active)
        target_record = self._validate_install_record(
            pack_id, target_path, expected_active=False
        )
        validate_installed_manifest_custody(self, target_record, target_path)
        snapshot = self._snapshot_pack_state(pack_id)
        try:
            if old_active is not None:
                self._mark_revision_inactive(pack_id, old_active.name)
            self._mark_revision_active(pack_id, revision_dir_name)
            link = self.active_symlink_path(pack_id)
            temporary_link = link.with_name(f".active.{pack_id}")
            if temporary_link.exists() or temporary_link.is_symlink():
                temporary_link.unlink(missing_ok=True)
            temporary_link.symlink_to(Path("revisions") / revision_dir_name)
            os.replace(temporary_link, link)
        except Exception:
            snapshot.restore()
            raise
        finally:
            snapshot.cleanup()

    # -- internal helpers ----------------------------------------------------

    def _read_active_record(self, pack_id: str) -> InstallRecord | None:
        """Read the install.json from the active revision, or return None."""
        rev = self.active_revision_path(pack_id)
        if rev is None:
            return None
        record_path = rev / ".astrid" / "install.json"
        if not record_path.is_file():
            return None
        try:
            data = _json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            return None
        try:
            record = InstallRecord.from_dict(data)
            if not _is_canonical_v2_record(record):
                return None
            if canonical_manifest_path(rev) is None:
                return None
            _validate_canonical_record_custody_metadata(self, record)
            return record
        except TypeError:  # noqa: BLE001
            return None
        except Exception as exc:  # noqa: BLE001
            log_and_swallow(exc, context="pack_store.load_record")
            return None


# ---------------------------------------------------------------------------
# No-op lock for environments without filelock
# ---------------------------------------------------------------------------


class _NoOpLock:
    """Context manager that does nothing (fallback when filelock is absent)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def installed_pack_roots() -> tuple[Path, ...]:
    """Return active canonical revision directories for installed packs."""
    store = InstalledPackStore()
    return store.active_pack_roots()


# ---------------------------------------------------------------------------
# Timestamp helpers (used by install.py)
# ---------------------------------------------------------------------------
def _revision_timestamp() -> str:
    """Return a compact UTC timestamp string suitable for revision dir names."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


__all__ = [
    "InstallRecord",
    "InstalledPackStore",
    "installed_pack_roots",
]
