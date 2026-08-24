# Replay: backup/restore live usage 2

Date: 2026-08-23 (Europe/Berlin)  
Scope: live CLI/agent UX only; no pytest, source inspection, or prior QA-report use.

## Verdict

**PASS.** The complete backup/restore workflow worked in two fresh temporary
roots. Restore rebased the managed-media locator automatically; the restored
image verified without `media relocate`, remained healthy after the original
source root was made unavailable, and the documented overwrite path (`--force`)
also restored successfully. `doctor` detected an intentionally stale locator
and returned a failing health result, then returned healthy after the file was
put back.

## Chronology and evidence

1. Created fresh roots (never used existing projects):
   - source: `/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/tmp.ERv0oLoKMM`
   - restore: `/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/tmp.KLOmCgFORU`
2. Read public `python3 -m astrid --help`, `doctor --json`, `backup --help`,
   `backup create --help`, and `backup restore --help`. The public census showed
   `backup restore <BACKUP_PATH> [--force]`; help describes `--force` as replacing
   a live database deliberately.
3. On the source root, created `recovery-demo` (`Recovery Demo`) and imported
   `tests/packs/builtin/generate_image/fixtures/tiny.png`.
   Import result: media id `a5e8b2eb-4bdf-5b9e-a919-fe48aa87f3b5`, SHA-256
   `b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640`, 69 bytes,
   managed locator under the source root. Source `doctor --json` was `ok: true`.
4. Created backup at
   `/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/astrid-recovery-backup-2`.
   The CLI reported `ok: true`, `media_files: 1`, `sqlite_pages: 87`, and four
   pack entries. Backup contained `backup.json` and `astrid.sqlite3`.
5. Restored into the clean restore root. Result was `ok: true`,
   `restored_media_files: 1`, `rebased_media_locators: 1`. The restored media
   locator pointed into the restore root, not the source root.
6. On the restored root, `doctor --json` was `ok: true` with accessible managed
   media, quick-check ok, no foreign-key violations, and all four schema packs
   at version 1. `projects list/show`, `media list/show`, and `media verify`
   all succeeded; verify preserved the 69-byte hash and required no relocate.
7. Made the original source root unavailable by moving it to
   `tmp.ERv0oLoKMM-source-unavailable-2` (the original path no longer existed).
   Re-ran restore-root `doctor --json` and `media verify`: both remained healthy,
   proving the restored project/media were independent of the source root.
8. Exercised overwrite behavior. Restoring over the populated restore root
   without `--force` was correctly refused (`restore_validation`, exit 1) with
   the user-facing instruction to use `--force`. Repeating with `--force`
   returned `ok: true`, `restored_media_files: 1`, `rebased_media_locators: 1`.
   Post-overwrite doctor and media verify were both healthy.
9. Stale-locator detection check: temporarily moved the restored managed media
   file out of its locator. `doctor --json` returned `ok: false`, exit 1, and
   explicitly reported that locator `01m0qmwn074rr7bbas3qx80699` did not resolve
   to a regular file. Restoring the file made doctor `ok: true` again, followed
   by a successful media verify.

## UX/friction notes

- The public help is discoverable and clearly documents the overwrite guard and
  `--force`; the no-force refusal is actionable.
- Restore output exposes the two most useful independence signals directly:
  `restored_media_files` and `rebased_media_locators`.
- No manual `media relocate` was needed. The only notable operational friction
  is that the initial brand-new-root doctor correctly reports missing data as a
  failure before the first project command initializes the store; its detail
  explains the expected next command.
- The stale-media doctor diagnostic is specific (locator id plus path and a
  restore/relocate remedy), and recovery is straightforward.

