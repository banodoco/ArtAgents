# Live UX wave: backup and restore (1)

Date: 2026-08-23 15:35–15:37 UTC

## Scope and isolation

This was live CLI usage as a fresh agent, not a test-suite or programmatic test. I used only these newly-created temporary roots:

- source `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-source.HIGCC6`
- clean restore `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-restore.w2DB3W`

The fixture was `tests/packs/builtin/generate_image/fixtures/tiny.png`. No source files were modified. The source media file was briefly renamed within the source temp root to test whether the restored copy was actually usable, then restored.

## Chronological journey (commands and observed results)

1. `python3 -m astrid --help` — clearly showed the eight families and exposed `backup create [--out]` and `backup restore <BACKUP_PATH> [--force]`.
2. `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-source.HIGCC6 python3 -m astrid doctor --json` — correctly reported a new root as unhealthy because `.astrid`/database did not exist, and suggested `projects create`.
3. `python3 -m astrid backup --help`; then `python3 -m astrid backup create --help`; then `python3 -m astrid backup restore --help` — useful syntax. Restore help explained that `--force` replaces a live database holding data, but did not explain what root is restored into or that media locators may need repair.
4. `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-source.HIGCC6 python3 -m astrid projects create recovery-demo --name "Recovery Demo" --json` — succeeded; project id `0a25970c-04f5-56c2-92cf-6d0e9714b7fc`. Read the generated `recovery-demo/plan.md` as the agent-facing orientation step.
5. `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-source.HIGCC6 python3 -m astrid media import tests/packs/builtin/generate_image/fixtures/tiny.png --project recovery-demo --json` — succeeded; media id `cb5d5a53-2492-55d3-9500-9ce6aaae2fb0`, hash `b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640`, 69 bytes, one managed-local location.
6. `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-source.HIGCC6 python3 -m astrid backup create` — succeeded. The only destination discovery was stdout: `/private/tmp/astrid-live-source.HIGCC6/.astrid/backups/backup-20260823-153536`; it reported one media file and 87 SQLite pages. There was no JSON envelope or machine-readable destination in this form.
7. `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-restore.w2DB3W python3 -m astrid backup restore /tmp/astrid-live-source.HIGCC6/.astrid/backups/backup-20260823-153536 --json` — succeeded, but `--json` was ignored: it printed a human-oriented object, not the documented five-key JSON envelope. It reported target `/private/tmp/astrid-live-restore.w2DB3W/.astrid/astrid.sqlite3` and one restored media file.
8. On the clean target, `doctor --json`, `projects show recovery-demo --json`, and `media list --project recovery-demo --json` all looked healthy. However, the media list still showed its locator as the *source* path (`...astrid-live-source...`), despite a copied file existing under the restore root.
9. `media verify <media-id> --project recovery-demo --realm managed_local --json` initially succeeded only because the source file still existed. To test real independence, I renamed the source file to `.source-held`; the same verify command returned `ok:false`, `internal_error`, `MediaPathError`, `prepared file must be a regular file`. This exposed a restore correctness bug: the restored database retained an absolute source-root media locator.
10. Used public help: `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-restore.w2DB3W python3 -m astrid media relocate --help`. It documented the supported recovery path (`--project`, `--realm managed_local`, `--locator`). Ran `media relocate <media-id> ... --locator /private/tmp/astrid-live-restore.w2DB3W/.astrid/media/sha256/b1/ff/<hash> --json`; it succeeded. With the source file held again, `media verify ... --json` then succeeded against the restored copy. This is the public-CLI recovery, without SQLite editing.
11. Re-ran restore into the now-populated restore target without force. It refused safely: `restore failed: refusing to restore over live data ... existing database already holds projects/events/media. Re-run with allow_overwrite=True (CLI: --force) ...`. Ran the same restore with `--force` deliberately, since this was an isolated disposable target; it succeeded and restored one media file. Force reset the repaired locator, so I repeated `media relocate` and `media verify` after the force restore.
12. Final evidence: `doctor --json` returned `ok:true`; all six checks passed (accessible target, managed-media tree, SQLite quick check, foreign keys, and `core=1, references=1, shots=1, timeline=1`). `projects show recovery-demo --json` returned the expected project. `media show <media-id> --project recovery-demo --json` returned the expected 69-byte PNG, hash, and restore-root locator; `media verify` passed.

## Severity-ranked UX critique

### P0 — restore silently leaves managed media pointing at the source root

The copied media is present and `doctor` passes, so the restored project initially appears healthy. But the first real media operation fails once the source disappears. A backup/restore that is not self-contained is a data-loss/availability hazard. Restore should rewrite managed-local locators to the destination root (or store relocatable paths), and should verify every copied media location before declaring success. At minimum, the restore result should explicitly warn: “N managed media records still point outside this projects root.”

### P1 — restore success does not prove media usability

“restored media files: 1” and a green doctor check were misleading. `doctor` checks the tree, not that database media locators resolve to it. Restore should run media verification and fail or clearly mark the backup incomplete when a locator is stale.

### P1 — `backup restore --json` is not JSON

The command accepts the global-looking `--json` but emits a non-envelope human response. The documented stable JSON surface raises an agent parsing trap. Either implement the envelope or reject `--json` with a clear usage error.

### P2 — default backup destination is discoverable only through prose stdout

The path was printed and usable, but there is no JSON destination field, and the help does not state the default naming/location convention. Add `backup_path`/`projects_root` to structured output and describe the default.

### P2 — root targeting should be explicit in the success narrative

The destination root came from `ASTRID_PROJECTS_ROOT`; the output did show it after the fact. Restore should print “restoring backup X into projects root Y” before mutation and include source/destination roots in its result. This would reduce the chance of restoring into the wrong configured root.

### P3 — force guard was good, but wording mixes SDK and CLI vocabulary

The refusal was safe and actionable, but says `allow_overwrite=True` before the CLI `--force` equivalent. Lead with the CLI flag and state exactly what is replaced (database, media, or both), plus a concise confirmation requirement.

## What Astrid should have told the agent

“This backup contains absolute managed-media paths. Restoring into a different `ASTRID_PROJECTS_ROOT` will copy the files but may leave database locators pointing to the old root. After restore, run `media list`, then `media verify` for each item. If locators still point to the old root, use `media relocate --realm managed_local --locator <destination file>`; we can offer an automatic `--rebase-media` repair. `backup restore --json` returns a five-key envelope containing source backup, destination root, database path, media count, and verification results. Re-running into a populated root is refused; `--force` replaces the target database and requires re-verification.”

## Outcome

Recovered successfully through public commands. Final restored project and media are usable and healthy after the required `media relocate`; final doctor and media verification pass. The main finding is P0: cross-root restore requires a manual locator repair that restore should perform automatically.
