# Replay: external backup portability 2 (fresh live black-box run)

## Verdict

**FAIL (portability PASS; verification gate FAIL).** Public backup/restore
portability, content-addressed external snapshot dedupe, provenance, atomic
failure, `--force` replacement, doctor, media identity, hashes, references,
associations, and rebasing all passed. The required media-verify gate does not
pass for the deduplicated media row with two external locations: the public
`media verify --realm external_local <media-id>` command returns typed
`conflict` instead of verifying both locations. The distinct external row and
managed row verify successfully. No source code or tests were changed.

## Scope and public surface

- Fresh disposable root: `.qa_tmp_replay_external_2.EEnyZf` under the repo.
- No source, tests, database edits, SDK calls, or private APIs; this used only
  `python3 -m astrid ...` and shell fixture/hash inspection.
- Started with `python3 -m astrid --help`, then inspected `backup`, `media`,
  and `media references` help.
- Project: `replay-external-2`, id
  `b503caa1-14d1-5c65-b279-46152edf818c`.

## Fixture and pre-backup evidence

Created four files through the public import flow:

| Realm | Fixture | Media id | Bytes | SHA-256 |
|---|---|---|---:|---|
| external_local | `duplicate-a.txt` | `8e5268e0-9eda-5dd4-bb6a-7f370c925c96` | 52 | `5727340e969cbb269e341a18d3c92883b87d3f46168f32e9d4cd134fd4f28b1d` |
| external_local | `duplicate-b.txt` | same media id (content dedupe) | 52 | same `5727340e...28b1d` |
| external_local | `distinct.txt` | `14ff9878-039a-5419-afab-860e3a20cd23` | 51 | `cf9baaf02a398d4cab2eeb9b5cb70c6a2d833fc8a6b7f034879a15a0a824fbc2` |
| managed_local | `managed.txt` | `1fdfaac0-7f8b-595d-9834-f91355f85197` | 31 | `533bf3de4ed5fc69619c17e4236ac594dad4163cee067504720eb96ffab023f0` |

`media list` showed 3 media rows and 4 locations: one external media row
with two distinct locators, one distinct external row, and one managed row.
Created two references (`Duplicate External`, `Distinct External`), their two
canonical associations, two additional media associations (managed `depicts`
and duplicate `inspired_by`), and one `related_to` reference link.

## Backup evidence

Command:

```text
ASTRID_PROJECTS_ROOT=.../source_projects \
  python3 -m astrid backup create --out .../backup
```

Result:

```text
media files: 1
external snapshots: 2 for 3 locator(s)
sqlite pages: 93
```

`backup/backup.json` reported `mode: self_contained`,
`external_dependencies: 3`, `external_dependencies_unresolved: 0`,
`external_media_files: 2`, and retained all three `original_locator` values:

- `.../source_external/duplicate-a.txt`
- `.../source_external/duplicate-b.txt`
- `.../source_external/distinct.txt`

Both duplicate entries pointed to the one snapshot path
`external/sha256/57/27/5727340e...28b1d`; the distinct entry pointed to
`external/sha256/cf/9b/cf9baaf...24fbc2`. Snapshot hashes matched the source
hashes exactly.

## Atomic negative cases

1. Moved `duplicate-a.txt` away and reran backup. It exited 1 with
   `external_local backup dependency is unavailable`; the requested output
   directory did not exist. Restoring the file made a retry succeed.
2. Changed `duplicate-b.txt` bytes and reran backup. It exited 1 with
   `external_local backup dependency changed` (expected hash `5727340e...`,
   found `c0999532...`); the output directory did not exist and the CLI said
   `no backup was published`. Restored the source bytes.
3. Mutated the duplicate snapshot in the backup and ran forced restore over a
   healthy target. It exited 1 with snapshot-integrity failure (51 bytes,
   expected 52) and `restore was not published`. Target SQLite SHA-256 stayed
   `76936c37e6e9df192e17e454bfafc4ad61b4f1f93ebf00373dc127c444dd32df` before
   and after; the media read model was byte-for-byte unchanged. The snapshot
   was restored before cleanup.

## Restore, force flow, and post-restore evidence

Deleted all four original external fixture files and the original external
directory before restore; the original root was absent thereafter.

```text
python3 -m astrid backup restore .../backup --projects-root .../restore_projects
```

Succeeded with `restored media files: 3`, `external snapshots: 2`,
`rebased locators: 3`, `unresolved: 0`. The restored duplicate locations
rebased to the managed storage tree:

- first locator: `.astrid/media/external/sha256/57/27/5727340e...28b1d`
- second locator: `.astrid/media/external/locators/2a7446adb193de848fb392fc36cdd12c52ae1be48a36d64e77657b93224bebe1`

The distinct external locator rebased to `.astrid/media/external/sha256/cf/9b/...`.
All restored bytes matched the three hashes above. Media IDs, content hashes,
location IDs, project id, reference IDs, canonical/secondary associations,
reference link, and metadata were preserved. `media show` exposed
`backup_provenance.external_local` with both original and restored locators.

For replacement coverage, created a sentinel project in a second target.
Restore without `--force` exited 1 and left the sentinel intact. Restore with
`--force` succeeded and replaced it with `replay-external-2`; the same 3 media,
2 external snapshots, and 3 rebased locators were present.

Final `doctor --json` was `ok: true` on both restore roots, with accessible
managed media, external integrity verified for 3 locators, SQLite quick-check
ok, no foreign-key violations, and all four schema versions valid.

## Verification gate and friction

```text
media verify --realm external_local 14ff9878-039a-5419-afab-860e3a20cd23  -> ok
media verify --realm managed_local  1fdfaac0-7f8b-595d-9834-f91355f85197 -> ok
media verify --realm external_local 8e5268e0-9eda-5dd4-bb6a-7f370c925c96 -> exit 1, conflict
```

The duplicate media row has two external locations, exactly the required
dedupe/dependency shape. The CLI's documented positional argument is a media
id (location ids return `not_found`), but verifying that media id returns
`{"ok":false,"error":{"code":"conflict","message":"the write conflicts with current state"}}`.
Thus doctor is green and two single-location media rows verify green, but the
deduplicated two-location row cannot be verified through the public CLI. This
is the sole failed acceptance gate and the reason for the overall FAIL verdict.

## Cleanup

The original external files/root were explicitly removed before restore. All
remaining disposable roots and backup copies were removed after evidence was
recorded; the requested report is the only durable artifact from this replay.
