# Replay: backup / restore / multi-location verify closure

Date: 2026-08-23
Surface: public `python3 -m astrid` CLI and read-only backup manifest inspection; no source, test, git, or prior-QA inspection.

## Verdict

PASS. A portable external backup restored cross-root with one content-deduped media row, two preserved `external_local` location identities, and its canonical reference association. Default aggregate verification covered both locations, precise `--location-id` and exact stored `--locator` selectors worked, the missing-locator failure produced the documented typed partial-success result, and selector-based repair returned doctor and aggregate verification to green.

## Fixture and backup

- Disposable root: `/tmp/astrid-replay-bv3-ZMQfJB`.
- Project slug: `replay` (project id `b8f95877-a40b-5960-ba91-4c149ce6c74c`).
- Imported identical 42-byte payloads from two different source paths using `--realm external_local`.
- Import deduped to one media row: `077f6a99-95dd-579e-bde8-3344645552cb`, SHA-256 `e5056d679030f939c3ec17317d5171daedfdd037a00567f72f29c7c4ac039ca0`.
- Location ids: `01m0r3vdw6nd0r1bfb2afpykpx` and `01m0r3vferb67axtj1bjcah0dv`.
- Created reference `4f08cbff-aa2e-5d9b-bf15-ef5764daee6e` (`Replay Shot`, kind `object`) with one primary `canonical` association to that media id.
- `backup create` reported `media files: 0`, `external snapshots: 1 for 2 locator(s)`, and 87 SQLite pages.
- `backup.json` independently reported `external_media_files=1`, `external_dependencies=2`, `external_dependencies_unresolved=0`, and two external records sharing one `media_path` and one `media_id`; both original locators were retained as provenance.

## Cross-root restore and healthy verification

The complete source root was removed before restore. `backup restore` into `/tmp/astrid-replay-bv3-ZMQfJB/dest-root` reported `restored media files: 1`, `external snapshots: 1`, `rebased locators: 2`, `unresolved: 0`. `media show` showed both original location ids, destination-owned locators, and `metadata.backup_provenance.external_local` entries mapping each original locator to its restored locator. The original source root no longer existed, and both live locators were under the destination root.

`media verify <media-id> --realm external_local --json` returned:

```text
ok=true, verified_count=2, failed_count=0, locations_total=2,
partial_success=false, locations_truncated=0
```

Precise verification succeeded with both `--location-id <location-id>` and the exact canonical destination `--locator <stored locator>` (the stored path is `/private/tmp/...`; the lexical `/tmp/...` alias is not the exact locator key).

## Missing locator and partial-success semantics

After deleting the second restored locator file, default aggregate verify exited 1 and returned:

```text
error.code=integrity_error
verified_count=1, failed_count=1, locations_total=2,
partial_success=true, locations_truncated=0
```

The error details contained both per-location candidates, the failed location id and locator, `mutation_policy="successful locations are committed independently; failed locations are unchanged"`, and recovery text instructing retry with `--location-id` or `--locator` after repair. The healthy location received a new `verified_at`; the failed location retained its prior `verified_at` exactly. The failed per-location error also said `no write occurred` and supplied recovery guidance to restore the external file or use `media relocate`.

## Repair and closure

The missing bytes were restored from the self-contained backup snapshot to the failed destination locator. Public selector verification with `media verify <media-id> --realm external_local --location-id 01m0r3vferb67axtj1bjcah0dv --json` succeeded, followed by default aggregate verify with `verified_count=2`, `failed_count=0`, and `partial_success=false`.

Final `doctor --json --strict-optional --projects-root <dest-root>` was green: data paths, media paths (`external_local integrity verified (2 locator(s))`), SQLite quick check, foreign keys, and schema versions all reported `ok`. `media references show` still showed the same reference with the same primary canonical association and media id. No source code was changed.
