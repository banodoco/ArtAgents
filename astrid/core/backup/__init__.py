"""Operational ``backup`` CLI family (m6 sprint plan, Phase 1).

Exposes the create/restore operations and their typed results. The dispatch
boundary (``astrid.core.gateway.dispatch._dispatch_backup``) lazy-imports
:mod:`astrid.core.backup.cli`; this package stays free of any repository or
writer import.
"""

from __future__ import annotations

from astrid.core.backup.operations import (
    BACKUP_DATABASE_NAME,
    BACKUP_FORMAT_VERSION,
    BACKUP_MEDIA_DIR,
    BACKUP_METADATA_NAME,
    BackupError,
    BackupResult,
    RestoreResult,
    RestoreValidationError,
    create_backup,
    restore_backup,
)

__all__ = [
    "BACKUP_DATABASE_NAME",
    "BACKUP_FORMAT_VERSION",
    "BACKUP_MEDIA_DIR",
    "BACKUP_METADATA_NAME",
    "BackupError",
    "BackupResult",
    "RestoreResult",
    "RestoreValidationError",
    "create_backup",
    "restore_backup",
]
