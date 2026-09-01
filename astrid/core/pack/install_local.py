"""Local install, uninstall, update, and rollback orchestration.

Extracted from ``install.py`` (M4 T20).  ``install.py`` re-exports
these names for callers.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.pack._common import SymlinkedPackPathError, reject_symlinked_path
from astrid.core.pack import pack_manifest_path
from astrid.core.pack.gitignore import gitignore_filter
from astrid.core.pack.install_git import (
    _install_from_git,
    _is_git_url,
    _update_git_pack,
)

# Leaf-level helpers imported directly from their real home modules
# (install_trust = pure leaf, install_git = git leaf).  ``_confirm`` and
# ``_confirm_trust`` are NOT imported here: they retain a late import from
# ``.install`` inside the functions that call them so that
# mock.patch("astrid.core.pack.install._confirm" / "._confirm_trust") still
# intercepts the call (the documented monkeypatch contract — see
# docs/contracts/monkeypatch-contracts.md §2).
from astrid.core.pack.install_trust import (
    _format_permission,
    _format_trust_summary,
    _normalized_summary_permissions,
    _trust_missing_error,
)
from astrid.core.pack.canonical import (
    CanonicalPackEntry,
    CanonicalPackValidationError,
    ExternalPackSource,
    _validate_staged_canonical_pack,
    canonical_manifest_path,
    read_normalize_validate,
)
from astrid.core.pack.manifest import (
    ManifestParseError,
    load_manifest_for_dispatch,
    load_manifest_mapping,
)
from astrid.core.pack.store import (
    InstalledPackStore,
    InstallRecord,
    _is_canonical_v2_record,
    _is_legacy_v1_schema,
    _manifest_path_for_installed_record,
    _revision_timestamp,
    validate_installed_manifest_custody as _validate_installed_manifest_custody_impl,
)
from astrid.core.pack.validate import extract_trust_summary, validate_pack
from astrid.core.util.time import utc_now_seconds


def _validate_installed_manifest_custody(
    store: InstalledPackStore,
    record: InstallRecord,
    pack_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
    propagate_canonical_errors: bool = False,
) -> CanonicalPackEntry | None:
    """Preserve the lifecycle patch seam over the shared custody validator."""
    return _validate_installed_manifest_custody_impl(
        store,
        record,
        pack_root,
        manifest_path=manifest_path,
        propagate_canonical_errors=propagate_canonical_errors,
        read_validate_fn=read_normalize_validate,
    )

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install_pack(
    source_path: str | Path,
    store: InstalledPackStore | None = None,
    *,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
    force: bool = False,
    git_url: str = "",
    commit_sha: str = "",
    requested_ref: str = "",
    source_type: str = "local",
    skip_name_check: bool = False,
    expected_pack_id: str | None = None,
) -> int:
    """Install a pack from a local directory or Git URL.

    Args:
        source_path: Path to the pack source directory, or a Git URL
            (``https://...``, ``git@...``, ``ssh://...``, ``git://...``).
        store: The ``InstalledPackStore`` to use.  Defaults to a new one.
        dry_run: If ``True``, print the trust summary and return 0 without
            mutating state.
        skip_confirm: If ``True``, skip the confirmation prompt.
        trust_acknowledged: If ``True``, skip the exact trust acknowledgement.
        trust_method: Audit label for the trust decision.
        trust_actor: Audit actor/source for the trust decision.
        force: If ``True``, overwrite an existing install (old revision is
            renamed to ``<pack_id>.<timestamp>``).
        git_url: Durable Git URL (set by the Git branch).
        commit_sha: Pinned commit SHA (set by the Git branch).
        requested_ref: Branch/tag requested at install time (set by the Git
            branch).
        source_type: ``"local"`` or ``"git"``.
        skip_name_check: If ``True``, skip the directory-name-matches-pack-id
            check (used when the source has already been staged).

    Returns:
        Exit code (0 on success).
    """
    if store is None:
        store = InstalledPackStore()

    # ── Late import from .install preserves the monkeypatch seams for
    # _confirm / _confirm_trust (mock.patch("astrid.core.pack.install.*")).
    # All other helpers (_format_trust_summary, _install_from_git, _is_git_url,
    # _trust_missing_error) are now module-level imports from their leaf homes.
    from astrid.core.pack.install import _confirm, _confirm_trust  # noqa: E402

    # ── Git URL detection MUST happen BEFORE Path().resolve() ──────────
    source_str = str(source_path)
    is_git = _is_git_url(source_str)
    if is_git:
        return _install_from_git(
            source_str,
            store,
            requested_ref=requested_ref or None,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=force,
        )

    try:
        source = reject_symlinked_path(Path(source_path).expanduser())
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"install source must not be a symlink or contain symlinked ancestors: "
            f"{source_path}"
        ) from exc
    source = source.resolve()
    manifest_path = canonical_manifest_path(source) or pack_manifest_path(source)
    if manifest_path is None:
        print(
            f"install: no pack manifest found in {source} "
            f"(expected pack.yaml, pack.yml, or pack.json)",
            file=sys.stderr,
        )
        return 2
    try:
        raw = load_manifest_for_dispatch(manifest_path, manifest_kind="pack")
    except ManifestParseError as exc:
        print(f"install: failed to parse pack manifest: {exc}", file=sys.stderr)
        return 2
    schema_version = raw.get("schema_version")
    if "schema_version" in raw and not (
        (type(schema_version) is int and schema_version == 1)
        or (type(schema_version) is float and schema_version == 1.0)
    ):
        try:
            load_manifest_mapping(
                manifest_path, manifest_kind="pack", reject_duplicate_keys=True
            )
        except ManifestParseError as exc:
            print(f"install: failed to parse pack manifest: {exc}", file=sys.stderr)
            return 2
        canonical_expected_pack_id = expected_pack_id
        if canonical_expected_pack_id is None and skip_name_check:
            manifest_id = raw.get("id")
            if isinstance(manifest_id, str):
                canonical_expected_pack_id = manifest_id
        return install_canonical_pack(
            source,
            store=store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=force,
            git_url=git_url,
            commit_sha=commit_sha,
            requested_ref=requested_ref,
            source_type=source_type,
            expected_pack_id=canonical_expected_pack_id,
        )

    pack_id = raw.get("id")
    if not isinstance(pack_id, str) or not pack_id:
        print(
            "install: pack manifest missing required 'id' field",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # 3. Source directory name must match pack id (PackResolver invariant)
    # ------------------------------------------------------------------
    if not skip_name_check and source.name != pack_id:
        print(
            f"install: source directory name {source.name!r} must match "
            f"pack id {pack_id!r} declared in pack manifest.",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # 4. Check collision
    # ------------------------------------------------------------------
    existing = store.get_active_strict(pack_id)
    if existing is not None and not force:
        print(
            f"install: pack {pack_id!r} is already installed.\n"
            f"  Installed at: {existing.installed_at}\n"
            f"  Source:       {existing.source_path}\n"
            f"  Use --force to overwrite (old revision will be preserved).",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------
    # 5. Extract trust summary
    # ------------------------------------------------------------------
    try:
        trust_summary = extract_trust_summary(source)
    except Exception as e:
        print(f"install: cannot extract trust summary: {e}", file=sys.stderr)
        return 2

    # ------------------------------------------------------------------
    # 6. Dry-run: print trust summary and exit
    # ------------------------------------------------------------------
    if dry_run:
        print(
            _format_trust_summary(
                trust_summary,
                git_url=git_url,
                commit_sha=commit_sha,
                astrid_version=str(raw.get("astrid_version", "")),
                trust_tier=source_type,
            )
        )
        return 0

    # ------------------------------------------------------------------
    # 7. Validate source pack
    # ------------------------------------------------------------------
    errors, warnings = validate_pack(source)
    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)

    if errors:
        print(
            f"install: source pack validation failed with {len(errors)} error(s):",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        print(
            "install: refusing to install an invalid pack.",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------
    # 8. Trust acknowledgement and ordinary confirmation
    # ------------------------------------------------------------------
    if not trust_acknowledged:
        if skip_confirm:
            _trust_missing_error("install", pack_id)
            return 1
        if not _confirm_trust(
            pack_id,
            {
                **trust_summary,
                "source_path": trust_summary.get("source_path", str(source)),
            },
        ):
            print("Cancelled.", file=sys.stderr)
            return 1
        trust_acknowledged = True
        trust_method = trust_method or "interactive"
        trust_actor = trust_actor or "cli"
    else:
        trust_method = trust_method or "api"
        trust_actor = trust_actor or "api"

    if not skip_confirm:
        action = "overwrite" if existing else "install"
        if not _confirm(f"Proceed with {action}?"):
            print("Cancelled.", file=sys.stderr)
            return 1

    # ------------------------------------------------------------------
    # 9. Acquire lock
    # ------------------------------------------------------------------
    lock = store._acquire_lock(pack_id)

    try:
        with lock:
            return _do_install(
                source, pack_id, trust_summary, store, force, existing,
                manifest_raw=raw,
                trust_method=trust_method,
                trust_actor=trust_actor,
                git_url=git_url,
                commit_sha=commit_sha,
                requested_ref=requested_ref,
                source_type=source_type,
            )
    except Exception:
        # Ensure no broken state — clean up staging if it exists
        staging = store.staging_path_for(pack_id)
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
        raise




def _assert_canonical_rollback_target_compatibility(
    current_record: InstallRecord,
    target_record: InstallRecord,
) -> None:
    """Reject a metadata-downgraded target before reading its manifest."""
    if _is_canonical_v2_record(current_record) and not _is_canonical_v2_record(
        target_record
    ):
        raise AstridError(
            f"active state is corrupt: canonical rollback target record for "
            f"pack {current_record.pack_id!r} is not canonical",
            code="pack.active_corrupt",
            recovery_command="inspect the pack's active pointer and install records",
        )




def _canonical_manifest_path_for_revision_target(
    record: InstallRecord,
    pack_root: Path,
    revisions_root: Path,
) -> Path | None:
    """Select only the canonical manifest from a confined rollback revision."""
    if not _is_canonical_v2_record(record):
        raise CanonicalPackValidationError(
            f"rollback target record for {record.pack_id!r} is not canonical"
        )
    if (
        not pack_root.is_absolute()
        or not revisions_root.is_absolute()
        or (
            pack_root.name == record.pack_id
            and record.active is not False
        )
        or record.revision != pack_root.name
    ):
        raise CanonicalPackValidationError(
            f"canonical rollback target identity is not confined to "
            f"{record.pack_id!r}: {pack_root}"
        )
    try:
        confined_root = reject_symlinked_path(pack_root)
        confined_revisions = reject_symlinked_path(revisions_root)
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"canonical rollback target must not be a symlink or contain "
            f"symlinked ancestors: {pack_root}"
        ) from exc
    try:
        resolved_root = confined_root.resolve(strict=False)
        resolved_revisions = confined_revisions.resolve(strict=False)
    except OSError as exc:
        raise CanonicalPackValidationError(
            f"canonical rollback target cannot be resolved: {pack_root}"
        ) from exc
    if (
        not confined_root.is_dir()
        or resolved_root.parent != resolved_revisions
        or not resolved_revisions.is_dir()
    ):
        raise CanonicalPackValidationError(
            f"canonical rollback target is not a direct revision of "
            f"{record.pack_id!r}: {pack_root}"
        )
    return canonical_manifest_path(confined_root)


def _canonical_trust_summary(entry: CanonicalPackEntry, source: Path) -> dict:
    definition = entry.definition
    return {
        "pack_id": definition.id,
        "name": definition.name,
        "version": definition.version,
        "schema_version": definition.schema_version,
        "source_path": str(source),
        "component_counts": {"resources": len(entry.resources)},
        "declared_secrets": [item["name"] for item in definition.secrets],
        "permissions": [
            {
                "id": item.id,
                "reason": item.reason,
                **({"access": item.access} if item.access is not None else {}),
                **({"services": list(item.services)} if item.services else {}),
            }
            for item in definition.permissions
        ],
    }


def install_canonical_pack(
    source_path: str | Path,
    store: InstalledPackStore | None = None,
    *,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
    force: bool = False,
    git_url: str = "",
    commit_sha: str = "",
    requested_ref: str = "",
    source_type: str = "local",
    expected_pack_id: str | None = None,
) -> int:
    """Install one canonical v2 external pack through the real store seam."""
    if store is None:
        store = InstalledPackStore()
    try:
        source = reject_symlinked_path(Path(source_path).expanduser())
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"install source must not be a symlink or contain symlinked ancestors: "
            f"{source_path}"
        ) from exc
    try:
        canonical_source = ExternalPackSource(source_type)
    except ValueError as exc:
        raise CanonicalPackValidationError(
            f"canonical install source type must be 'local' or 'git', got {source_type!r}"
        ) from exc
    if canonical_source not in (ExternalPackSource.LOCAL, ExternalPackSource.GIT):
        raise CanonicalPackValidationError(
            f"canonical install source type must be 'local' or 'git', got {source_type!r}"
        )
    preflight = read_normalize_validate(
        source / "pack.yaml",
        source=canonical_source,
        resolve_resources=False,
        expected_pack_id=expected_pack_id,
    )
    try:
        store.assert_revisions_root(preflight.id)
    except AstridError as exc:
        raise CanonicalPackValidationError(str(exc)) from exc
    try:
        store.assert_install_target(preflight.id)
    except AstridError as exc:
        print(f"install: publication failed: {exc}", file=sys.stderr)
        return 1
    existing = store.get_active_strict(preflight.id)
    entry = read_normalize_validate(
        source / "pack.yaml",
        source=canonical_source,
        resolve_resources=True,
        expected_pack_id=expected_pack_id,
    )
    source = entry.root
    pack_id = entry.id
    trust_summary = _canonical_trust_summary(entry, source)
    if source_type == "git" and git_url:
        trust_summary["source_path"] = git_url

    if existing is not None and not force:
        print(f"install: pack {pack_id!r} is already installed.", file=sys.stderr)
        return 1
    if dry_run:
        print(
            _format_trust_summary(
                trust_summary,
                git_url=git_url,
                commit_sha=commit_sha,
                trust_tier=source_type,
            )
        )
        return 0

    from astrid.core.pack.install import _confirm, _confirm_trust

    if not trust_acknowledged:
        if skip_confirm:
            _trust_missing_error("install", pack_id)
            return 1
        if not _confirm_trust(pack_id, trust_summary):
            print("Cancelled.", file=sys.stderr)
            return 1
        trust_acknowledged = True
        trust_method = trust_method or "interactive"
        trust_actor = trust_actor or "cli"
    else:
        trust_method = trust_method or "api"
        trust_actor = trust_actor or "api"
    if not skip_confirm and not _confirm("Proceed with install?"):
        print("Cancelled.", file=sys.stderr)
        return 1

    lock = store._acquire_lock(pack_id)
    try:
        with lock:
            return _do_install(
                source,
                pack_id,
                trust_summary,
                store,
                force,
                existing,
                manifest_raw=entry.definition.to_dict(),
                trust_method=trust_method,
                trust_actor=trust_actor,
                source_type=source_type,
                git_url=git_url,
                commit_sha=commit_sha,
                requested_ref=requested_ref,
                canonical_entry=entry,
            )
    except Exception:
        staging = store.staging_path_for(pack_id)
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def _do_install(
    source: Path,
    pack_id: str,
    trust_summary: dict,
    store: InstalledPackStore,
    force: bool,
    existing: InstallRecord | None,
    *,
    git_url: str = "",
    commit_sha: str = "",
    requested_ref: str = "",
    source_type: str = "local",
    manifest_raw: dict | None = None,
    trust_method: str | None = None,
    trust_actor: str | None = None,
    canonical_entry: CanonicalPackEntry | None = None,
) -> int:
    """Perform the actual install (called under lock)."""
    install_root = store.install_root_for(pack_id)
    revisions_dir = store.revisions_dir(pack_id)
    staging = store.staging_path_for(pack_id)

    try:
        # Reject an unconfined direct target before snapshotting, reading its
        # record, rotating it, or publishing through it.
        store.assert_install_target(pack_id)
    except AstridError as exc:
        print(f"install: publication failed: {exc}", file=sys.stderr)
        return 1

    publication_snapshot = store._snapshot_pack_state(pack_id)
    snapshot_restored = False

    def restore_previous_install() -> None:
        """Restore every mutable publication entry to its pre-install state."""
        nonlocal snapshot_restored
        if not snapshot_restored:
            publication_snapshot.restore()
            snapshot_restored = True

    # Derive trust_tier from source_type
    trust_tier = source_type  # "local" or "git"

    # Compute the digest from the manifest admission selected above.
    manifest_path = (
        canonical_manifest_path(source)
        if canonical_entry is not None
        else pack_manifest_path(source)
    )
    manifest_digest = ""
    if manifest_path is not None and manifest_path.is_file():
        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    # Derive astrid_version from manifest raw dict
    astrid_version = ""
    if manifest_raw:
        astrid_version = str(manifest_raw.get("astrid_version", ""))

    # last_validation_time: record that we validated before install
    last_validation_time = utc_now_seconds()
    trust_acknowledged_at = utc_now_seconds()
    permissions_accepted = _normalized_summary_permissions(trust_summary)
    no_sandbox_warning_version = 1

    # Clean up any leftover staging
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)

    # Ensure directory structure
    install_root.mkdir(parents=True, exist_ok=True)
    revisions_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 10. Copy to staging with gitignore filter
    # ------------------------------------------------------------------
    try:
        shutil.copytree(
            source,
            str(staging),
            ignore=gitignore_filter(source),
            symlinks=True,
        )
    except Exception as e:
        print(f"install: copy to staging failed: {e}", file=sys.stderr)
        # Restore any pre-existing staging and publication entries.
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
        restore_previous_install()
        publication_snapshot.cleanup()
        return 1

    # ------------------------------------------------------------------
    # 11. Validate staging
    # ------------------------------------------------------------------
    if canonical_entry is None:
        errors, _warnings = validate_pack(staging)
        if errors:
            print(
                f"install: staging validation failed with {len(errors)} error(s):",
                file=sys.stderr,
            )
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            restore_previous_install()
            publication_snapshot.cleanup()
            return 1
    else:
        try:
            _validate_staged_canonical_pack(staging, pack_id)
        except Exception as exc:
            print(f"install: staging validation failed: {exc}", file=sys.stderr)
            restore_previous_install()
            publication_snapshot.cleanup()
            return 1

    # ------------------------------------------------------------------
    # 12–15. Publish the revision and its custody atomically.
    # ------------------------------------------------------------------

    previous_active_revision = ""
    active_link = store.active_symlink_path(pack_id)
    rev_target = revisions_dir / pack_id
    temporary_link = active_link.with_name(f".active.{pack_id}")

    # Re-read the pointer under the install lock.  ``existing`` was admitted
    # before locking and is not authoritative for the publication target.
    preinstall_record = store.get_active_strict(pack_id)
    old_rev_dir = (
        store.active_revision_path(pack_id)
        if preinstall_record is not None
        else None
    )
    displaced_active_revision: str | None = None
    displaced_active_record: InstallRecord | None = preinstall_record

    # For Git installs, source_path stores the durable git_url (not temp path).
    source_path_str = git_url if source_type == "git" and git_url else str(source)
    record = InstallRecord(
        pack_id=pack_id,
        name=trust_summary.get("name", pack_id),
        version=str(trust_summary.get("version", "0.0.0")),
        schema_version=trust_summary.get("schema_version", 1),
        source_path=source_path_str,
        installed_at=utc_now_seconds(),
        revision=pack_id,
        install_root=str(install_root),
        active=True,
        component_inventory=trust_summary.get("component_counts", {}),
        entrypoints=trust_summary.get("entrypoints", []),
        declared_secrets=trust_summary.get("declared_secrets", []),
        dependencies=trust_summary.get("dependencies", []),
        trust_summary=trust_summary,
        manifest_digest=manifest_digest,
        source_type=source_type,
        git_url=git_url,
        commit_sha=commit_sha,
        requested_ref=requested_ref,
        astrid_version=astrid_version,
        trust_tier=trust_tier,
        last_validation_time=last_validation_time,
        previous_active_revision="",
        trust_acknowledged_at=trust_acknowledged_at,
        trust_method=trust_method or "api",
        trust_actor=trust_actor or "api",
        no_sandbox_warning_version=no_sandbox_warning_version,
        permissions_accepted=permissions_accepted,
    )

    def publish_pointer(target: Path) -> None:
        """Atomically point ``active`` at a fully recorded revision."""
        if temporary_link.exists() or temporary_link.is_symlink():
            temporary_link.unlink(missing_ok=True)
        temporary_link.symlink_to(os.path.relpath(target, active_link.parent))
        os.replace(temporary_link, active_link)

    try:
        if preinstall_record is not None:
            if old_rev_dir is None or not old_rev_dir.is_dir():
                raise AstridError(
                    f"active revision for pack {pack_id!r} is unavailable",
                    code="pack.active_corrupt",
                )
            if old_rev_dir.name != preinstall_record.revision:
                raise AstridError(
                    f"active revision for pack {pack_id!r} has mismatched custody",
                    code="pack.active_corrupt",
                )

            # A direct target is copied first so the old pointer remains valid
            # while its target is replaced.  A timestamped active revision is
            # already the durable rollback target and must not be duplicated.
            if old_rev_dir == rev_target:
                ts = _revision_timestamp()
                renamed = revisions_dir / f"{pack_id}.{ts}"
                counter = 1
                while renamed.exists():
                    renamed = revisions_dir / f"{pack_id}.{ts}.{counter}"
                    counter += 1
                shutil.copytree(old_rev_dir, renamed, symlinks=True)
                # ``preinstall_record`` was admitted from the strict active
                # pointer above.  Carry that exact custody record to the
                # rotated directory instead of rediscovering it after a
                # publication mutation.
                copied_record = preinstall_record
                copied_record.revision = renamed.name
                copied_record.active = True
                store._write_revision_record(pack_id, renamed.name, copied_record)
                publish_pointer(renamed)
                shutil.rmtree(old_rev_dir)
                displaced_active_revision = renamed.name
                displaced_active_record = copied_record
            else:
                displaced_active_revision = preinstall_record.revision
                displaced_active_record = preinstall_record
            if displaced_active_revision != displaced_active_record.revision:
                raise AstridError(
                    f"active revision for pack {pack_id!r} has mismatched custody",
                    code="pack.active_corrupt",
                )
            previous_active_revision = displaced_active_revision

        # Preserve any existing direct target as an inactive revision.  This
        # is distinct from the actual active revision when the pointer names a
        # timestamped rollback target.
        if rev_target.exists():
            displaced_record = store._read_revision_record(pack_id, rev_target.name)
            displaced = revisions_dir / f"{pack_id}.{_revision_timestamp()}"
            counter = 1
            while displaced.exists() or displaced == old_rev_dir:
                displaced = revisions_dir / f"{pack_id}.{_revision_timestamp()}.{counter}"
                counter += 1
            rev_target.rename(displaced)
            if displaced_record is not None:
                displaced_record.revision = displaced.name
                displaced_record.active = False
                store._write_revision_record(pack_id, displaced.name, displaced_record)

        # The new tree is complete, including its strict record, before the
        # active pointer can expose it.
        staging.rename(rev_target)
        if canonical_entry is not None:
            _validate_staged_canonical_pack(rev_target, pack_id)
        record.revision = pack_id
        record.previous_active_revision = previous_active_revision
        store.record_install(record)
        publish_pointer(rev_target)

        if displaced_active_revision is not None:
            if displaced_active_record is None:
                raise AstridError(
                    f"active revision for pack {pack_id!r} has no retained record",
                    code="pack.active_corrupt",
                )
            # Use the revision retained from the strict active pointer.  Do
            # not rediscover a different record after publication.
            store._mark_revision_inactive(
                pack_id,
                displaced_active_record.revision,
                record=displaced_active_record,
            )
    except Exception as exc:
        restore_previous_install()
        print(f"install: publication failed: {exc}", file=sys.stderr)
        publication_snapshot.cleanup()
        return 1

    publication_snapshot.cleanup()

    # ------------------------------------------------------------------
    # 16. Print success
    # ------------------------------------------------------------------
    print(
        _format_trust_summary(
            trust_summary,
            git_url=git_url,
            commit_sha=commit_sha,
            astrid_version=astrid_version,
            trust_tier=trust_tier,
        )
    )
    print()
    print(f"✓ Pack {pack_id!r} installed successfully.")
    print(f"  Location: {install_root}")
    return 0


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_pack(
    pack_id: str,
    store: InstalledPackStore | None = None,
    *,
    keep_revisions: bool = False,
    skip_confirm: bool = False,
) -> int:
    """Uninstall a pack.

    Args:
        pack_id: The pack to uninstall.
        store: The ``InstalledPackStore`` to use.
        keep_revisions: If ``True``, leave the revisions directory.
        skip_confirm: If ``True``, skip the confirmation prompt.

    Returns:
        Exit code.
    """
    if store is None:
        store = InstalledPackStore()

    # Late import preserves the mock.patch("astrid.core.pack.install._confirm") seam.
    from astrid.core.pack.install import _confirm  # noqa: E402

    existing = store.get_active_strict(pack_id)
    if existing is None:
        print(
            f"uninstall: pack {pack_id!r} is not installed.",
            file=sys.stderr,
        )
        return 1

    if not skip_confirm:
        print(f"Pack:  {existing.name} ({existing.pack_id})")
        print(f"Ver:   {existing.version}")
        print(f"From:  {existing.source_path}")
        if not _confirm(f"Uninstall {pack_id!r}?"):
            print("Cancelled.", file=sys.stderr)
            return 1

    lock = store._acquire_lock(pack_id)
    with lock:
        store.remove_install(pack_id, keep_revisions=keep_revisions)

    print(f"✓ Pack {pack_id!r} uninstalled.")
    return 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def _format_update_diff(
    old_summary: dict,
    new_summary: dict,
    *,
    old_version: str = "",
    new_version: str = "",
    old_commit: str = "",
    new_commit: str = "",
) -> str:
    """Produce a human-readable diff between two trust summaries.

    Args:
        old_summary: Trust summary for the currently installed revision.
        new_summary: Trust summary for the candidate (would-be-installed)
            revision.
        old_version: Semantic version string for the old revision.
        new_version: Semantic version string for the new revision.
        old_commit: Commit SHA (or empty) for the old revision.
        new_commit: Commit SHA (or empty) for the new revision.

    Returns:
        A formatted multi-line string suitable for console display.
    """
    lines: list[str] = []
    lines.append("═══ Diff Summary ═══")

    # Version change
    if old_version != new_version:
        lines.append(f"  Version:  {old_version} → {new_version}")
    else:
        lines.append(f"  Version:  {old_version} (unchanged)")

    # Commit SHA change (Git only)
    if old_commit and new_commit and old_commit != new_commit:
        lines.append(
            f"  Commit:   {old_commit[:8]} → {new_commit[:8]}"
        )
    elif old_commit and new_commit:
        lines.append(f"  Commit:   {old_commit[:8]} (unchanged)")

    # Component count deltas
    old_counts = old_summary.get("component_counts", {})
    new_counts = new_summary.get("component_counts", {})
    for kind in ("executors", "orchestrators", "elements"):
        old_n = old_counts.get(kind, 0)
        new_n = new_counts.get(kind, 0)
        if old_n != new_n:
            delta = new_n - old_n
            sign = "+" if delta > 0 else ""
            lines.append(f"  {kind.capitalize()}:{old_n} → {new_n} ({sign}{delta})")
        else:
            lines.append(f"  {kind.capitalize()}:{old_n} (unchanged)")

    # Entrypoint additions/removals
    old_eps = set(old_summary.get("entrypoints", []))
    new_eps = set(new_summary.get("entrypoints", []))
    added_eps = new_eps - old_eps
    removed_eps = old_eps - new_eps
    if added_eps:
        lines.append(f"  Entrypoints added:   {', '.join(sorted(added_eps))}")
    if removed_eps:
        lines.append(f"  Entrypoints removed: {', '.join(sorted(removed_eps))}")
    if not added_eps and not removed_eps and old_eps:
        lines.append("  Entrypoints: (unchanged)")

    # Declared secrets deltas
    old_secrets = set(old_summary.get("declared_secrets", []))
    new_secrets = set(new_summary.get("declared_secrets", []))
    added_secrets = new_secrets - old_secrets
    removed_secrets = old_secrets - new_secrets
    if added_secrets:
        lines.append(f"  Secrets added:   {', '.join(sorted(added_secrets))}")
    if removed_secrets:
        lines.append(f"  Secrets removed: {', '.join(sorted(removed_secrets))}")
    if not added_secrets and not removed_secrets and (old_secrets or new_secrets):
        lines.append("  Secrets: (unchanged)")

    old_permissions = {
        str(permission.get("id", "?")): permission
        for permission in _normalized_summary_permissions(old_summary)
        if permission.get("id")
    }
    new_permissions = {
        str(permission.get("id", "?")): permission
        for permission in _normalized_summary_permissions(new_summary)
        if permission.get("id")
    }
    added_permission_ids = sorted(set(new_permissions) - set(old_permissions))
    removed_permission_ids = sorted(set(old_permissions) - set(new_permissions))
    changed_permission_ids = sorted(
        permission_id
        for permission_id in set(old_permissions) & set(new_permissions)
        if old_permissions[permission_id] != new_permissions[permission_id]
    )
    if added_permission_ids:
        lines.append("  Permissions added:")
        for permission_id in added_permission_ids:
            lines.append(f"    - {_format_permission(new_permissions[permission_id])}")
    if removed_permission_ids:
        lines.append("  Permissions removed:")
        for permission_id in removed_permission_ids:
            lines.append(f"    - {_format_permission(old_permissions[permission_id])}")
    if changed_permission_ids:
        lines.append("  Permissions changed:")
        for permission_id in changed_permission_ids:
            lines.append(
                "    - "
                f"{permission_id}: {_format_permission(old_permissions[permission_id])} "
                f"→ {_format_permission(new_permissions[permission_id])}"
            )
    if (
        not added_permission_ids
        and not removed_permission_ids
        and not changed_permission_ids
    ):
        if old_permissions or new_permissions:
            lines.append("  Permissions: (unchanged)")
        else:
            lines.append("  Permissions: none declared")

    return "\n".join(lines)


def _diff_component_inventories(
    old_summary: dict,
    new_summary: dict,
    *,
    old_version: str = "",
    new_version: str = "",
    old_commit: str = "",
    new_commit: str = "",
) -> str:
    """Backward-compatible wrapper for the update diff formatter."""
    return _format_update_diff(
        old_summary,
        new_summary,
        old_version=old_version,
        new_version=new_version,
        old_commit=old_commit,
        new_commit=new_commit,
    )


def update_pack(
    pack_id: str,
    store: InstalledPackStore | None = None,
    *,
    dry_run: bool = False,
    skip_confirm: bool = False,
    trust_acknowledged: bool = False,
    trust_method: str | None = None,
    trust_actor: str | None = None,
) -> int:
    """Update an installed pack from its source.

    Args:
        pack_id: The pack to update.
        store: The ``InstalledPackStore`` to use.
        dry_run: If ``True``, print a diff summary without mutating.
        skip_confirm: If ``True``, skip confirmation.
        trust_acknowledged: If ``True``, skip the exact trust acknowledgement.
        trust_method: Audit label for the trust decision.
        trust_actor: Audit actor/source for the trust decision.

    Returns:
        Exit code.
    """
    if store is None:
        store = InstalledPackStore()

    existing = store.get_active_strict(pack_id)
    if existing is None:
        print(
            f"update: pack {pack_id!r} is not installed.",
            file=sys.stderr,
        )
        return 1

    try:
        _validate_installed_manifest_custody(store, existing)
    except CanonicalPackValidationError as exc:
        raise store._active_corrupt(
            f"installed manifest custody for pack {pack_id!r} is invalid"
        ) from exc
    except AstridError:
        raise

    # ── Branch: Git-backed packs ──────────────────────────────────────
    if existing.source_type == "git":
        return _update_git_pack(
            existing, pack_id, store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
        )

    # ── Local-path packs ──────────────────────────────────────────────
    source_path = Path(existing.source_path)
    if _is_canonical_v2_record(existing):
        # The installed record fixes the parser family.  A canonical record
        # can only update from a strictly valid confined v2 pack.yaml.
        try:
            manifest_path = _manifest_path_for_installed_record(existing, source_path)
        except CanonicalPackValidationError as exc:
            print(f"update: canonical source custody rejected: {exc}", file=sys.stderr)
            return 2
        if manifest_path is None:
            print(
                f"update: no canonical pack manifest found in source {source_path}",
                file=sys.stderr,
            )
            return 2
        try:
            entry = read_normalize_validate(
                manifest_path,
                source=ExternalPackSource.LOCAL,
                resolve_resources=True,
                expected_pack_id=pack_id,
            )
        except Exception as exc:
            print(f"update: canonical source validation failed: {exc}", file=sys.stderr)
            return 2
        if dry_run:
            print("═══ Currently Installed ═══")
            print(f"  Version:  {existing.version}")
            print(f"  Source:   {existing.source_path}")
            print(f"  Installed:{existing.installed_at}")
            print()
            print("═══ Source (would install) ═══")
            print(
                _format_trust_summary(
                    _canonical_trust_summary(entry, entry.root),
                    git_url=existing.git_url,
                    commit_sha=existing.commit_sha,
                    trust_tier=existing.trust_tier or existing.source_type,
                )
            )
            return 0
        return install_pack(
            source_path,
            store=store,
            dry_run=False,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=True,
        )

    if not source_path.is_dir():
        print(
            f"update: source directory {source_path} no longer exists. "
            f"Cannot update.",
            file=sys.stderr,
        )
        return 1
    manifest_path = _manifest_path_for_installed_record(existing, source_path)
    if manifest_path is None:
        print(
            f"update: no pack manifest found in source {source_path}",
            file=sys.stderr,
        )
        return 2
    try:
        raw = load_manifest_for_dispatch(manifest_path, manifest_kind="pack")
    except ManifestParseError as e:
        print(f"update: failed to parse pack manifest: {e}", file=sys.stderr)
        return 2
    schema_version = raw.get("schema_version")
    is_legacy_v1 = _is_legacy_v1_schema(schema_version)
    if "schema_version" in raw and not is_legacy_v1:
        return install_pack(
            source_path,
            store=store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=True,
        )
    # Extract trust summary for display
    try:
        trust_summary = extract_trust_summary(source_path)
    except Exception as e:
        print(f"update: cannot extract trust summary: {e}", file=sys.stderr)
        return 2

    # Dry-run: print diff
    if dry_run:
        print("═══ Currently Installed ═══")
        print(f"  Version:  {existing.version}")
        print(f"  Source:   {existing.source_path}")
        print(f"  Installed:{existing.installed_at}")
        print()
        print("═══ Source (would install) ═══")
        print(
            _format_trust_summary(
                trust_summary,
                git_url=existing.git_url,
                commit_sha=existing.commit_sha,
                astrid_version=str(raw.get("astrid_version", "")),
                trust_tier=existing.trust_tier or existing.source_type,
            )
        )
        return 0

    # Real update: same flow as install with force
    return install_pack(
        source_path,
        store=store,
        dry_run=False,
        skip_confirm=skip_confirm,
        trust_acknowledged=trust_acknowledged,
        trust_method=trust_method,
        trust_actor=trust_actor,
        force=True,
    )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback_pack(
    pack_id: str,
    store: InstalledPackStore | None = None,
    *,
    revision: str | None = None,
    skip_confirm: bool = False,
) -> int:
    """Rollback an installed pack to a previous revision.

    Args:
        pack_id: The pack to rollback.
        store: The ``InstalledPackStore`` to use.
        revision: The revision directory name to activate.  When ``None``
            (the default), the user is shown a numbered list of available
            revisions and asked to choose one interactively.
        skip_confirm: If ``True``, skip the confirmation prompt (the
            revision selection prompt is still shown when *revision* is
            ``None``).

    Returns:
        Exit code (0 on success).
    """
    if store is None:
        store = InstalledPackStore()

    # Late import preserves the mock.patch("astrid.core.pack.install._confirm") seam.
    from astrid.core.pack.install import _confirm  # noqa: E402

    existing = store.get_active_strict(pack_id)
    if existing is None:
        print(
            f"rollback: pack {pack_id!r} is not installed.",
            file=sys.stderr,
        )
        return 1
    active_rev = store.active_revision_path(pack_id)
    if active_rev is None:
        raise store._active_corrupt(
            f"active revision for pack {pack_id!r} is unavailable"
        )
    _validate_installed_manifest_custody(store, existing, active_rev)
    current_rev_name = active_rev.name
    prevalidated_custody: tuple[InstallRecord, InstallRecord] | None = None
    if revision is not None:
        if revision == current_rev_name:
            print(
                f"rollback: revision {revision!r} is already active.",
                file=sys.stderr,
            )
            return 1
        prevalidated_custody = store.assert_rollback_custody(pack_id, revision)

    # List available revisions only after the specifically requested target
    # has passed custody validation.
    revisions = store.list_revisions(pack_id)
    if not revisions:
        print(
            f"rollback: no revisions found for pack {pack_id!r}.",
            file=sys.stderr,
        )
        return 1

    # ── Revision selection ────────────────────────────────────────────
    target_rev_name: str | None = revision

    if target_rev_name is None:
        # Interactive: show numbered prompt
        print(f"Available revisions for {pack_id!r}:")
        for i, rev_path in enumerate(revisions, start=1):
            rev_name = rev_path.name
            marker = " ← active" if rev_name == current_rev_name else ""
            # Validate revision metadata and manifest custody before showing
            # revision details through the interactive lifecycle surface.
            try:
                rec = store._validate_install_record(
                    pack_id,
                    rev_path,
                    expected_active=(rev_name == current_rev_name),
                )
                if rec is not None:
                    _validate_installed_manifest_custody(store, rec, rev_path)
            except AstridError:
                rec = None
            if rec is not None:
                print(
                    f"  [{i}] {rev_name}  "
                    f"v{rec.version}  "
                    f"{rec.installed_at}{marker}"
                )
            else:
                print(f"  [{i}] {rev_name}{marker}")

        print()
        try:
            choice = input(
                "Choose revision number (or press Enter to cancel): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            return 1

        if not choice:
            print("Cancelled.", file=sys.stderr)
            return 1

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(revisions):
                print(
                    f"rollback: invalid choice {choice!r}. "
                    f"Must be between 1 and {len(revisions)}.",
                    file=sys.stderr,
                )
                return 1
        except ValueError:
            print(
                f"rollback: invalid choice {choice!r}.",
                file=sys.stderr,
            )
            return 1

        target_rev_name = revisions[idx].name

    # Validate target selection and both custody records before reading target
    # content or displaying output.  In particular, targets must be inactive.
    if target_rev_name is None:
        print("rollback: no revision selected.", file=sys.stderr)
        return 1

    # An explicitly requested target was already admitted before listing.
    # Interactive selection is admitted here, after the safe name-only list.
    if target_rev_name == current_rev_name:
        print(
            f"rollback: revision {target_rev_name!r} is already active.",
            file=sys.stderr,
        )
        return 1
    if prevalidated_custody is None:
        current_record, target_record = store.assert_rollback_custody(
            pack_id, target_rev_name
        )
    else:
        current_record, target_record = prevalidated_custody
    current_root = store.active_revision_path(pack_id)
    if current_root is None:
        raise store._active_corrupt(
            f"active revision for pack {pack_id!r} is unavailable"
        )
    _validate_installed_manifest_custody(store, current_record, current_root)
    _assert_canonical_rollback_target_compatibility(current_record, target_record)
    target_path = store.revisions_dir(pack_id) / target_rev_name
    try:
        if _is_canonical_v2_record(target_record):
            target_manifest = _canonical_manifest_path_for_revision_target(
                target_record,
                target_path,
                store.assert_revisions_root(pack_id),
            )
        else:
            target_manifest = _manifest_path_for_installed_record(
                target_record, target_path
            )
    except CanonicalPackValidationError as exc:
        print(f"rollback: canonical target custody rejected: {exc}", file=sys.stderr)
        return 1
    if target_manifest is None:
        try:
            _validate_installed_manifest_custody(
                store, target_record, target_path
            )
        except AstridError as exc:
            print(f"rollback: target pack validation failed: {exc}", file=sys.stderr)
            return 1
        return 1

    try:
        target_entry = _validate_installed_manifest_custody(
            store,
            target_record,
            target_path,
            manifest_path=target_manifest,
        )
    except AstridError as exc:
        print(f"rollback: target pack validation failed: {exc}", file=sys.stderr)
        return 1

    if target_entry is None:
        # Legacy records retain the v1 dispatch and validation behavior.
        try:
            target_raw = load_manifest_for_dispatch(
                target_manifest, manifest_kind="pack"
            )
            target_schema = target_raw.get("schema_version")
            target_is_v1 = _is_legacy_v1_schema(target_schema)
        except Exception as exc:
            print(f"rollback: target pack validation failed: {exc}", file=sys.stderr)
            return 1

        if target_entry is None:
            errors, _warnings = validate_pack(target_path)
            if errors:
                print(
                    f"rollback: target pack validation failed with {len(errors)} error(s) "
                    "— the revision may be incompatible with the current Astrid version.",
                    file=sys.stderr,
                )
                for error in errors:
                    print(f"  {error}", file=sys.stderr)
                print(
                    "rollback: the rollback has been applied, but the pack may not "
                    "function correctly.",
                    file=sys.stderr,
                )
    target_summary = (
        _canonical_trust_summary(target_entry, target_path)
        if target_entry is not None
        else extract_trust_summary(target_path)
    )

    old_summary = existing.trust_summary if existing.trust_summary else {}
    target_version = target_record.version
    old_commit = existing.commit_sha
    target_commit = target_record.commit_sha
    print("═══ Currently Active ═══")
    print(f"  Revision:  {current_rev_name}")
    print(f"  Version:   {existing.version}")
    if old_commit:
        print(f"  Commit:    {old_commit[:8]}")
    print(f"  Source:    {existing.source_path}")
    print()

    print("═══ Target Revision ═══")
    print(f"  Revision:  {target_rev_name}")
    print(f"  Version:   {target_version}")
    if target_commit:
        print(f"  Commit:    {target_commit[:8]}")
    if target_record is not None:
        print(f"  Source:    {target_record.source_path}")
    print()

    # Structured diff
    print(
        _diff_component_inventories(
            old_summary,
            target_summary,
            old_version=existing.version,
            new_version=target_version,
            old_commit=old_commit,
            new_commit=target_commit,
        )
    )
    print()

    # ── Confirmation ──────────────────────────────────────────────────
    if not skip_confirm:
        if not _confirm(
            f"Rollback {pack_id!r} to revision {target_rev_name!r}?"
        ):
            print("Cancelled.", file=sys.stderr)
            return 1

    # ── Perform rollback ──────────────────────────────────────────────
    lock = store._acquire_lock(pack_id)
    try:
        with lock:
            store.rollback_to_revision(pack_id, target_rev_name)
    except FileNotFoundError as e:
        print(f"rollback: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"rollback: unexpected error: {e}", file=sys.stderr)
        return 1

    new_active = store.active_revision_path(pack_id)
    if new_active is not None:
        if target_entry is not None:
            try:
                _validate_staged_canonical_pack(new_active, pack_id)
            except Exception as exc:
                print(f"rollback: rolled-back pack validation failed: {exc}", file=sys.stderr)
                return 1
        else:
            errors, warnings = validate_pack(new_active)
            if warnings:
                for warning in warnings:
                    print(f"warning: {warning}", file=sys.stderr)
            if errors:
                print(
                    f"rollback: rolled-back pack validation failed with "
                    f"{len(errors)} error(s) — the revision may be incompatible "
                    "with the current Astrid version.",
                    file=sys.stderr,
                )
                for error in errors:
                    print(f"  {error}", file=sys.stderr)
                print(
                    "rollback: the rollback has been applied, but the pack may "
                    "not function correctly.",
                    file=sys.stderr,
                )
                return 1

    print(f"✓ Pack {pack_id!r} rolled back to revision {target_rev_name!r}.")
    print(f"  Location: {store.install_root_for(pack_id)}")
    return 0


