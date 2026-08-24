# Final live acceptance 6 — cross-domain maker journey

Date: 2026-08-24 (Europe/Berlin)  
Mode: live product usage by public `python3 -m astrid` CLI only; no tests,
source edits, direct repositories, or pack `run.py` calls.  The requested
acceptance report itself is the only workspace artifact intentionally written.

## Verdict

**PASS with P1 portability and P2 discoverability findings — 7.5/10.**

The complete journey succeeded in disposable roots: discovery/help, doctor,
project routing, managed image/video/audio imports, canonical timeline CAS
history/diff, visualization, canonical version-pinned render, durable output
and provenance readback, stale-version rejection, archive/unarchive, portable
backup/restore, restored visualization, and a successful restored render after
repairing stale absolute registry paths.  The kernel was the authority in all
successful run/task records; no filesystem run projection was treated as an
authority.

Disposable roots:

- source: `/private/tmp/astrid-live-QhExrg`
- backup: `/tmp/astrid-live-backup-BLp11l/studio-backup`
- restored: `/private/tmp/astrid-live-restore-XRP8fg`

## Journey evidence

### Discover, bootstrap, and route a project

`astrid --version` returned `astrid`; top-level `--help` exposed the five
product families, three operational families, nested `timelines shots` and
`media references`, and the JSON envelope.  On the empty root,
`doctor --json` correctly reported missing `.astrid`/SQLite and gave the
initialization hint.  After `projects create studio --name "Live Studio"`,
doctor became green: SQLite quick check, FK integrity, managed paths, and
`core=1, references=1, shots=1, timeline=1` schema versions.

`projects list/show/select/current` all worked.  `projects select` created a
workspace preference at `Astrid/.astrid/config.json`, outside the disposable
root; this was an unexpected state mutation for a fresh-root test.  It was
removed after the journey.  Restored `projects current` still reported that
workspace preference path, although it correctly resolved the restored
project by slug and path.

### Media and canonical timeline

Three extension-recognized tiny files were imported as managed media:

- image `e0d629b5-b596-5b2d-be09-a9dcb9a7d5bd`, hash
  `4aef5e51da300acfcb8f05ae5ed5a12c3d68ad78657eac3ff7a9dda06d72b796`;
- video `26717682-57aa-5864-be91-b7ed09b99c14`;
- audio `f3fd3b53-7059-505b-96d1-eb810d5f439b`.

The repository fixture video/audio were 5-byte Git-LFS pointer files.  Astrid
accepted them as media by extension; rendering failed only later.  I then
created valid one-second MP4/WAV files locally and imported them as managed
video `30b0d9ef-d545-5251-8860-14f8173df341` and audio
`5d460c95-e236-5b61-b40f-4e44f6684e5a`.  This is a real late-validation
friction: import did not establish decodability.

`timelines create primary --default` succeeded.  `timelines save` CAS advanced
the timeline through versions 2–8 while converging on a renderer-compatible
document with visual/audio tracks and managed-media registry paths.  The
canonical final source document had three `clipType: "media"` clips and
`output.resolution: "1920x1080"`.  `timelines show`, `history`, and `diff`
returned coherent document/registry changes and lifecycle versions.

The first visualization attempt used intuitive `assetId` clip fields and
failed with a detailed JSON-schema error saying `assetId` was unexpected.  A
recovery save using the documented `asset` field made visualization succeed.
`timelines visualize primary --format all --json` produced a durable manifest,
PNG/SVG pages, ground truth, indexes, diagnostics, and pack hashes in managed
content-addressed media.

### Canonical render and run ledger

`timelines render primary --expected-version 8 --output-name live-studio.mp4`
succeeded as run `4ebd03674d7f845f85ab0fcbae`, task
`3dc3f98103d61376f52b2dd789`.  `runs show --evidence` returned the bounded
child outputs:

| Output | Media ID | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `out/live-studio.mp4` | `01m0sjgwaznwmgfavvy5rx8jj3` | 391127 | `97303a3cfb01eb57ea608fded7f83af8073fbdfb4eeaaad8b7186c50181b6faa` |
| `out/live-studio.mp4.provenance.json` | `01m0sjgwb6t2m1jgga02f85a8k` | 18938 | `96fcdac76eb61b29f0f5c1a4de9f05622b9c665cbde694ca41fe5f46c71964a2` |

`tasks events` showed queued → claimed → started → completed with output
hashes, and `runs show` included the canonical timeline authority:
`authority=kernel`, timeline UUID/ULID/slug, `config_version=8`, config hash,
registry hash, materialized registry hash, head event ID, and head hash.  The
render was a real kernel-admitted run, not a filesystem-run shortcut.

### Stale recovery and reversible lifecycle

Rendering with `--expected-version 7` while the head was 8 failed before
admission with a typed `validation_error`; all kernel run/task IDs were null
and the message instructed the operator to show the timeline and retry with
the current version.  No render run was created by this stale attempt.

`timelines archive` advanced to version 9; active list became empty and
`--include-archived` recovered the timeline.  `unarchive` advanced to version
10 and a repeated unarchive returned `changed: false`, proving idempotence.

### Backup, restore, and restored readback

`backup create` staged a portable backup with 35 media files and 178 SQLite
pages.  Restoring into `/private/tmp/astrid-live-restore-XRP8fg` succeeded;
doctor was green, managed-media locators resolved, projects/timeline/media
rows were present, and the restored image verified successfully.

Restored `timelines show/history/diff` and `timelines visualize` succeeded and
produced new durable visualization artifacts.  The first restored canonical
render failed before renderer execution because the persisted registry still
contained source-root absolute paths such as
`/tmp/astrid-live-QhExrg/.astrid/media/...`; the resolver explicitly reported
the path was outside the restored project root and not an owned managed
locator.  I repaired this through the public CAS path by saving the unchanged
timeline document with restored managed paths at version 11.  The second
render succeeded as run `dd403c7fe4e0a8e51e12f30461`, task
`c5039810cc71bfecb252895cc4`, with output `restored-studio.mp4` and provenance
sidecar.  The restored run authority recorded `config_version=11`, a new
config hash, registry/materialized hashes, head event ID
`ac0c95e91f204f33b0948f79bfd68c0b`, and head hash
`9ad041a4d5543ffb6bb25067ded4c32f990c5da1b02ed4a666019a902e58b32a`.

## Severity-ranked findings

### P1 — backup restore does not rebase absolute timeline registry paths

The documented portable restore copied/rebased managed media rows, but a
timeline registry containing absolute `file` paths remained source-rooted.
The first restored canonical render failed until a user performed a manual
CAS save with destination-root paths.  A portable backup should rewrite or
materialize these locators automatically, or reject source-absolute registry
entries at save time with a recovery path.  This is the only material gap in
the requested cross-root flow.

### P1 — media import accepts undecodable extension-only files

The imported 5-byte `.mp4`/`.wav` files were accepted and persisted as media;
the failure appeared much later inside Remotion.  A lightweight probe or a
clear `metadata.probe` integrity state would make the error immediate and
avoid admitting doomed render work.

### P2 — canonical timeline schema requires trial-and-error

Family help exposes whole-document CAS but not a minimal media timeline. The
natural `assetId` form was accepted by timeline save and failed only during
visualization. The schema error was excellent and recovery was straightforward,
but an example in `timelines save --help` or a preflight command would reduce
agent/user wrong turns.

### P2 — project selection writes outside `ASTRID_PROJECTS_ROOT`

`projects select` is intentionally file-side, but its default workspace scope
writes under the checkout even when all product data is isolated under a
disposable root. This is surprising in a fresh-root acceptance run and made
restored `projects current` report a preference path outside the restored root.
The selection itself remained safe and did not route to the wrong project.

## Kernel authority / legacy authority check

All successful render/run/task records were read through `runs`, `tasks`, and
`media` CLI surfaces. Canonical render task specs explicitly stamped
`"authority": "kernel"` and timeline identity/version/hash authority. Stale
render rejection occurred before run admission. No filesystem `run.json`,
JSONL event log, legacy task-mode command, or legacy filesystem store was used
or treated as authoritative. Doctor and post-restore managed-media checks
agreed with the kernel read models.

## Final score

| Area | Result |
| --- | ---: |
| discovery/bootstrap/doctor | 8/10 |
| project/media/timeline CRUD and CAS | 8/10 |
| visualization and render ledger | 8/10 |
| stale/archive lifecycle | 9/10 |
| backup/restore portability | 6/10 |
| authority/provenance/readback | 8/10 |
| **overall** | **7.5/10 — PASS with P1 follow-up** |

