# External-local backup portability fix

Date: 2026-08-23 (Europe/Berlin)

## Live reproduction

Fresh disposable CLI usage created a project, imported a file as
`external_local`, created a backup, restored it into a separate projects root,
and removed the original external file. Before this fix:

- `backup create` reported `media_files: 0` and contained no copy of the
  external file;
- restore preserved the absolute source locator and reported success;
- `doctor` was green only while the original source still existed;
- after removing the source, `doctor` failed `media_paths` with an unavailable
  external locator.

This was a real agent-UX portability failure: a successful restore could not be
used on a machine without the original host path.

## Root fix

`backup create` now snapshots every readable `external_local` locator into a
deduplicated `media/external/sha256/<digest>` tree inside the staged backup.
Each dependency is hashed before and after copying; missing, symlinked, or
mutated sources fail before the backup publication marker can publish a new
destination. The source is never written.

`backup.json` retains the original locator, media id, location id, content hash,
size, and snapshot path for every dependency. It reports both unique external
snapshot count and locator dependency count. Same-content external locations
share one snapshot.

Restore validates every snapshot before the database/media swap. It rebases
external locators to verified backup-owned bytes under the destination
`.astrid/media` tree and records the original locator in
`media.metadata_json.backup_provenance.external_local`. If multiple location
rows share one snapshot, the first uses the digest path and the rest receive
stable hard-link aliases, preserving location rows while keeping bytes
deduplicated. Database and media publication remains one journaled atomic
swap, including `--force` replacement of a populated target root.

Older backups without an `external` section remain readable; their external
rows are left as unresolved host dependencies and the restore result reports
`unresolved_external_locators`.

## Verification

Fresh live replay with two different external paths containing identical bytes:

- backup: `external_media_files: 1`, `external_dependencies: 2`, one snapshot
  file, two original locator records;
- cross-root `--force` restore: `restored_external_files: 1`,
  `rebased_external_locators: 2`, `unresolved_external_locators: 0`;
- original external files removed after restore;
- target `doctor --json`: all checks `ok`, including external integrity for
  both locations;
- restored media retained one media id/content hash, two location rows, and
  original locator provenance.

Failure probes are atomic:

- missing or mutated source during backup raises a typed `BackupError` and
  publishes no backup directory;
- mutating a backup snapshot causes `RestoreValidationError` before a forced
  restore changes a populated target.

Targeted regressions: `18 passed` from
`tests/v10/test_backup_external_portability.py` plus
`tests/v10/test_backup_restore.py`.

The follow-up replay found and fixed the public multi-location verification
gate for this deduped shape; see
`findings/media-verify-multilocation-fix.md`.

Changed surfaces:

- `astrid/core/backup/operations.py`
- `astrid/core/backup/cli.py`
- `astrid/packs/_core/skill/SKILL.md`
- `docs/guides/cli-journeys.md`
- `tests/v10/test_backup_external_portability.py`
