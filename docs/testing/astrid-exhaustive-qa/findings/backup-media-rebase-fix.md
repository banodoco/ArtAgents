# Backup media rebase fix

Date: 2026-08-23

## Root cause

`backup create` copied the managed-media digest tree and the SQLite database
independently. `media_locations.locator` is an absolute path, so restoring the
database into another `ASTRID_PROJECTS_ROOT` left each `managed_local` row
pointing at the source root. The destination file existed, and the old doctor
only checked the destination directory shape, so this could look healthy until
the source file disappeared.

## Fix

`restore_backup` now rebases every staged `managed_local` locator to the
destination digest-derived path before publication. It verifies that every
referenced copied file is a regular file and that its SHA-256 matches the
database content hash. Any invalid hash, missing/corrupt copied file, or SQL
update failure raises an actionable `RestoreValidationError` while the staged
transaction is unpublished; the live database and media tree remain untouched.

Doctor's `media_paths` check now also verifies that managed locators point into
the current root's canonical digest tree and resolve to regular files. A stale
absolute locator fails doctor with the expected destination and recovery hint.

## Changed files

- `astrid/core/backup/operations.py` — staged managed-media rebase/integrity
  verification; restore result reports `rebased_media_locators`.
- `astrid/core/doctor.py` — managed locator health check and actionable detail.
- `tests/v10/test_backup_restore.py` — cross-root restore and stale-locator
  regression coverage.

## Live evidence

Using fresh temporary roots and the real CLI, I created `recovery-demo`,
imported `tiny.png`, created a backup, and restored into a second root. Restore
reported `rebased_media_locators: 1`; `media list` showed the target-root
locator. I held the source digest file unavailable, then `doctor --json`,
`media show`, and `media verify --realm managed_local` all succeeded against
the restored copy. Replaying the restore with `--force --json` again reported
one rebased locator and doctor remained fully green.

The narrow regression tests pass: `15 passed` in
`tests/v10/test_backup_restore.py`; the existing doctor integration suite also
passes (`16 passed` across backup/doctor integration tests).

## Residual JSON UX

`backup restore --json` now emits the machine-readable JSON object already
used by the CLI, including destination root, database path, restored file
count, and rebased locator count. `backup create --json` likewise emits its
destination path. The remaining UX gap is that these operational JSON results
are not the SDK's five-key `ok/data/error/receipt/idempotency_key` envelope;
they retain the backup-specific result shape. Human output and help still do
not expose a separate structured progress event before publication.
