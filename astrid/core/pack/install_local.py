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

import yaml

from astrid.core.pack import pack_manifest_path
# Trust helpers are imported via late imports from .install inside each
# function so that mock.patch("astrid.core.pack.install._confirm") and similar
# monkeypatch seams continue to work (M4 T20 / SD3).
from astrid.core.pack.store import (
    InstalledPackStore,
    InstallRecord,
    _revision_timestamp,
)
from astrid.core.util.time import utc_now_seconds
from astrid.core.pack.gitignore import gitignore_filter
from astrid.core.pack.validate import extract_trust_summary, validate_pack


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

    # ── Late imports from .install to preserve monkeypatch seams (M4 T20/T22 / SD3)
    # _install_from_git and _is_git_url are now in install_git.py (T22) but
    # re-exported via install.py so these late imports continue to work.
    from astrid.core.pack.install import (  # noqa: E402
        _confirm,
        _confirm_trust,
        _format_trust_summary,
        _install_from_git,
        _is_git_url,
        _trust_missing_error,
    )

    # ── Git URL detection MUST happen BEFORE Path().resolve() ──────────
    source_str = str(source_path)
    is_git = _is_git_url(source_str)

    if is_git:
        return _install_from_git(
            source_str,
            store,
            dry_run=dry_run,
            skip_confirm=skip_confirm,
            trust_acknowledged=trust_acknowledged,
            trust_method=trust_method,
            trust_actor=trust_actor,
            force=force,
        )

    source = Path(source_path).resolve()

    # ------------------------------------------------------------------
    # 1. Resolve the pack manifest
    # ------------------------------------------------------------------
    manifest_path = pack_manifest_path(source)
    if manifest_path is None:
        print(
            f"install: no pack manifest found in {source} "
            f"(expected pack.yaml, pack.yml, or pack.json)",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # 2. Parse manifest with yaml.safe_load directly (NOT load_pack_manifest)
    # ------------------------------------------------------------------
    try:
        if manifest_path.suffix == ".json":
            import json as _json

            raw = _json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"install: failed to parse pack manifest: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw, dict):
        print(
            "install: pack manifest is not a mapping", file=sys.stderr
        )
        return 2

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
    existing = store.get_active(pack_id)
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
) -> int:
    """Perform the actual install (called under lock)."""
    # Late imports from .install to preserve monkeypatch seams (M4 T20 / SD3)
    from astrid.core.pack.install import (  # noqa: E402
        _format_trust_summary,
        _normalized_summary_permissions,
    )

    install_root = store.install_root_for(pack_id)
    revisions_dir = store.revisions_dir(pack_id)
    staging = store.staging_path_for(pack_id)

    # Derive trust_tier from source_type
    trust_tier = source_type  # "local" or "git"

    # Compute manifest_digest from pack manifest file
    manifest_path = pack_manifest_path(source)
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
        # Clean up partial staging
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
        return 1

    # ------------------------------------------------------------------
    # 11. Validate staging
    # ------------------------------------------------------------------
    errors, _warnings = validate_pack(staging)
    if errors:
        print(
            f"install: staging validation failed with {len(errors)} error(s):",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        shutil.rmtree(staging, ignore_errors=True)
        return 1

    # ------------------------------------------------------------------
    # 12. Handle force: rename old revision
    # ------------------------------------------------------------------
    previous_active_revision = ""
    if existing is not None:
        old_rev_dir = store.active_revision_path(pack_id)
        if old_rev_dir is not None and old_rev_dir.is_dir():
            ts = _revision_timestamp()
            renamed = revisions_dir / f"{pack_id}.{ts}"
            try:
                old_rev_dir.rename(renamed)
                previous_active_revision = renamed.name
            except OSError as e:
                print(
                    f"install: cannot rename old revision: {e}",
                    file=sys.stderr,
                )
                shutil.rmtree(staging, ignore_errors=True)
                return 1

        # Remove old active symlink
        store.mark_inactive(pack_id)

    # ------------------------------------------------------------------
    # 13. Move staging → revisions/<pack_id>/
    # ------------------------------------------------------------------
    rev_target = revisions_dir / pack_id
    if rev_target.exists():
        shutil.rmtree(rev_target, ignore_errors=True)

    try:
        staging.rename(rev_target)
    except OSError as e:
        print(f"install: move staging to revisions failed: {e}", file=sys.stderr)
        shutil.rmtree(staging, ignore_errors=True)
        return 1

    # ------------------------------------------------------------------
    # 14. Create active symlink
    # ------------------------------------------------------------------
    active_link = store.active_symlink_path(pack_id)
    if active_link.exists() or active_link.is_symlink():
        active_link.unlink(missing_ok=True)

    active_link.symlink_to(
        os.path.relpath(rev_target, active_link.parent)
    )

    # ------------------------------------------------------------------
    # 15. Write .astrid/install.json
    # ------------------------------------------------------------------
    # For Git installs, source_path stores the durable git_url (not temp path)
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
        previous_active_revision=previous_active_revision,
        trust_acknowledged_at=trust_acknowledged_at,
        trust_method=trust_method or "api",
        trust_actor=trust_actor or "api",
        no_sandbox_warning_version=no_sandbox_warning_version,
        permissions_accepted=permissions_accepted,
    )
    store.record_install(record)

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

    # Late import from .install to preserve monkeypatch seams (M4 T20 / SD3)
    from astrid.core.pack.install import _confirm  # noqa: E402

    existing = store.get_active(pack_id)
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
    # Late imports from .install to preserve monkeypatch seams (M4 T20 / SD3)
    from astrid.core.pack.install import (  # noqa: E402
        _format_permission,
        _normalized_summary_permissions,
    )

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

    # Late imports from .install to preserve monkeypatch seams (M4 T20 / SD3)
    from astrid.core.pack.install import _format_trust_summary  # noqa: E402

    existing = store.get_active(pack_id)
    if existing is None:
        print(
            f"update: pack {pack_id!r} is not installed.",
            file=sys.stderr,
        )
        return 1

    # ── Branch: Git-backed packs ──────────────────────────────────────
    if existing.source_type == "git":
        # Late import to avoid circular dependency with .install (M4 T20/T22)
        # _update_git_pack is now in install_git.py (T22) but re-exported via install.py.
        from astrid.core.pack.install import _update_git_pack  # noqa: E402

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
    if not source_path.is_dir():
        print(
            f"update: source directory {source_path} no longer exists. "
            f"Cannot update.",
            file=sys.stderr,
        )
        return 1

    # Verify source pack id matches installed pack id
    manifest_path = pack_manifest_path(source_path)
    if manifest_path is None:
        print(
            f"update: no pack manifest found in source {source_path}",
            file=sys.stderr,
        )
        return 2

    try:
        if manifest_path.suffix == ".json":
            import json as _json

            raw = _json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"update: failed to parse pack manifest: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw, dict):
        print("update: pack manifest is not a mapping", file=sys.stderr)
        return 2

    source_pack_id = raw.get("id")
    if source_pack_id != pack_id:
        print(
            f"update: source pack id {source_pack_id!r} does not match "
            f"installed pack id {pack_id!r}. Refusing to update — "
            f"the pack identity has changed.",
            file=sys.stderr,
        )
        return 1

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

    # Late import from .install to preserve monkeypatch seams (M4 T20 / SD3)
    from astrid.core.pack.install import _confirm  # noqa: E402

    existing = store.get_active(pack_id)
    if existing is None:
        print(
            f"rollback: pack {pack_id!r} is not installed.",
            file=sys.stderr,
        )
        return 1

    # List available revisions
    revisions = store.list_revisions(pack_id)
    if not revisions:
        print(
            f"rollback: no revisions found for pack {pack_id!r}.",
            file=sys.stderr,
        )
        return 1

    # Determine the current active revision
    active_rev = store.active_revision_path(pack_id)
    current_rev_name = active_rev.name if active_rev is not None else None

    # ── Revision selection ────────────────────────────────────────────
    target_rev_name: str | None = revision

    if target_rev_name is None:
        # Interactive: show numbered prompt
        print(f"Available revisions for {pack_id!r}:")
        for i, rev_path in enumerate(revisions, start=1):
            rev_name = rev_path.name
            marker = " ← active" if rev_name == current_rev_name else ""
            # Try to read the revision record for a short description
            rec = store._read_revision_record(pack_id, rev_name)
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

    # Validate target exists
    if target_rev_name is None:
        print("rollback: no revision selected.", file=sys.stderr)
        return 1

    target_path = store.revisions_dir(pack_id) / target_rev_name
    if not target_path.is_dir():
        print(
            f"rollback: revision {target_rev_name!r} does not exist.",
            file=sys.stderr,
        )
        return 1

    # Reject rolling back to the currently active revision
    if target_rev_name == current_rev_name:
        print(
            f"rollback: revision {target_rev_name!r} is already active.",
            file=sys.stderr,
        )
        return 1

    # ── Validate target pack manifest ─────────────────────────────────
    target_manifest = pack_manifest_path(target_path)
    if target_manifest is None:
        print(
            f"rollback: no pack manifest found in target revision "
            f"{target_rev_name!r}.",
            file=sys.stderr,
        )
        return 1

    # ── Extract trust summaries for current and target ────────────────
    try:
        target_summary = extract_trust_summary(target_path)
    except Exception as e:
        print(
            f"rollback: cannot extract trust summary from target: {e}",
            file=sys.stderr,
        )
        return 1

    old_summary = existing.trust_summary if existing.trust_summary else {}

    # Read target revision record for version etc.
    target_record = store._read_revision_record(pack_id, target_rev_name)
    target_version = target_record.version if target_record is not None else str(
        target_summary.get("version", "?")
    )

    old_commit = existing.commit_sha
    target_commit = target_record.commit_sha if target_record is not None else ""

    # ── Display trust summaries and diff ──────────────────────────────
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

    # ── Re-validate the rolled-back pack ──────────────────────────────
    new_active = store.active_revision_path(pack_id)
    if new_active is not None:
        errors, warnings = validate_pack(new_active)
        if warnings:
            for w in warnings:
                print(f"warning: {w}", file=sys.stderr)
        if errors:
            print(
                f"rollback: rolled-back pack validation failed with "
                f"{len(errors)} error(s) — the revision may be "
                f"incompatible with the current Astrid version.",
                file=sys.stderr,
            )
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            print(
                "rollback: the rollback has been applied, but the pack "
                "may not function correctly.",
                file=sys.stderr,
            )
            return 1

    print(f"✓ Pack {pack_id!r} rolled back to revision {target_rev_name!r}.")
    print(f"  Location: {store.install_root_for(pack_id)}")
    return 0


