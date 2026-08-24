# Timeline restore consumability fix

Date: 2026-08-24 (Europe/Berlin)  
Scope: public CLI live reproduction and replay, followed by narrow regressions.

## Verdict

**PASS.** A portable restore now immediately recreates the non-authoritative
project workspace binding needed by file-oriented capabilities, and managed
timeline visualization resolves a stale pre-restore CAS locator by canonical
project ownership plus content hash. Timeline rows, version history, event
hashes, receipts, timeline UUID/ULID, and config versions are not rewritten.

## Original live failure

Fresh public journey:

1. `projects create restore-demo`
2. import PNG with `media import --realm managed_local`
3. `timelines create primary --default` with a media clip and the returned
   absolute managed locator
4. `timelines visualize ... --filmstrip assets` (succeeded before backup)
5. `backup create`, then restore into a different root
6. `doctor`, `timelines show`, and `timelines history` (all succeeded)
7. `timelines visualize` (failed before admission)

The exact failure was:

```text
project not found: 'restore-demo'; create it before visualizing a timeline
```

The restored root held the healthy kernel/media state under `.astrid`, but no
`restore-demo/project.json` or `restore-demo/plan.md`. In addition,
`timelines show` correctly preserved its immutable source-era registry payload,
whose `file` value named the old root; the mutable media-location projection
had correctly moved to the restored root.

## Correction

### Derived project workspace

Project workspace materialization now lives in one shared core helper used by
both project creation and restore. Restore derives `project.json` from the
kernel `projects` row, stamps `kernel_authority: true`, and creates the
documented `plan.md` skeleton only when no human plan exists. Existing
extension fields in a JSON binding are preserved; existing `plan.md` content
is never overwritten.

This step runs only after the journaled database/media swap succeeds. A staged
validation or publication failure therefore does not mutate target project
directories. The projection operation is idempotent. If the filesystem fails
after database/media publication, the error explicitly says that the
authoritative restore succeeded and instructs the operator to fix the path and
repeat the same restore with `--force` to reconcile projections.

The legacy `project.json.default_timeline_id` remains null because that old
file schema accepts uppercase filesystem ULIDs, while the kernel default is a
UUID-backed setting and current public timeline ULIDs are lowercase. The
kernel setting remains the only default authority and visualization selects it
correctly.

### Read-time managed-locator derivation

A shared read-only resolver accepts managed media only when all of these hold:

- the active kernel project owns a media row with the recorded content hash;
- that row has a `managed_local` location equal to this root's canonical
  digest-derived path;
- the path is a regular non-symlink file;
- its current bytes hash to the recorded digest.

Kernel timeline selection uses that resolver to return a derived registry copy
when a stored locator visibly has Astrid's managed CAS shape. It does not
update `timelines.asset_registry_json`, timeline events, event hashes, or
receipts. Timeline snapshot hashing, integrity classification, re-verification,
and filmstrip sampling recognize the same exact authorized locator. MIME type
from the registry is passed to the sampler because CAS filenames intentionally
have no extension.

Unrelated absolute paths, sibling-project media, paths without a recorded
digest, stale paths not recognized as managed CAS locators, and hash-mismatched
bytes continue to fail closed.

## Fresh live replay

Backup: `/tmp/astrid-timeline-restore-backup.Qx9ZRS`  
Restored root: `/tmp/astrid-timeline-restore-fixed.WV7xTJ`  
Original root was moved away before the final reads, so its recorded locator
was unavailable.

Restore JSON reported:

```text
restored_project_workspaces: 1
rebased_media_locators: 11
restored_media_files: 11
```

Public evidence after the original root became unavailable:

- `doctor --json`: every required check passed.
- `timelines show primary`: same timeline UUID
  `c8fd5719-4e75-59db-8279-d1cbeaf0dd82`, ULID
  `c1agv6n0h16esn1jws10vcg5j6`, `config_version: 1`, and source-era registry
  payload.
- `timelines history primary`: same single `timeline.created` version with the
  original config/registry.
- `media verify`: media `5fde73f1-37c6-57f2-8e1c-dd90f0528474` verified at the
  restored locator with hash
  `7c8b663e8f53967c8d2fb360f2e763780f7839ef2e6efef95c513163481fed76`.
- `timelines visualize --format md --layout linear --filmstrip assets`:
  succeeded as run `1ea6ee1f8ee5dcaff7b9215386`, task
  `dac62e6d487388c4fb56ac1009`.
- Visualization diagnostics contained `KERNEL_AUTHORITY` pinned to stream
  version 1, source event `2ac07438c78b46ab8699ee1a42a54246`, event hash
  `fad896a65c24d76e1d466218137144f1fdae80487c7c5feefaf9e2b221688f4b`;
  no `MEDIA_MISSING`, `UNSUPPORTED_MEDIA`, or hash warning remained.
- Ground truth recorded `verified_original` for the asset.
- Filmstrip output reused the exact original media ID and content hash above,
  proving the restored verified bytes—not the unavailable old path—were read.

## Regression coverage

- Cross-root restore creates `project.json`/`plan.md` and reports one restored
  workspace.
- A stale managed timeline registry locator derives the restored locator by
  exact project ownership and digest.
- A non-managed foreign path with the same filename/digest shape is unchanged
  and not authorized.
- Existing source-contained timeline media behavior remains covered by the
  timeline resolution/snapshot/visualizer suites.

Final focused verification: **174 passed** across backup/restore, managed
media resolution, timeline resolution/snapshot, visualization integrity,
selector purity, and project workspace tests. `py_compile` passed for every
changed Python module and `git diff --check` was clean.
