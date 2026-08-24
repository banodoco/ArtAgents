# Timeline registry restore portability root fix

Date: 2026-08-24 (Europe/Berlin)  
Finding: P1 from `waves/final-live-acceptance-6.md`  
Verdict: **FIXED — fresh cross-root restore visualizes and renders without a
timeline save or history rewrite.**

## Live failure reproduced before source inspection

The reproduction used only the public `python3 -m astrid` gateway. A source
project imported a tiny PNG into managed media, created canonical timeline
`main` at version 2, and stored this ordinary registry entry:

```json
{
  "assets": {
    "hero": {
      "file": "/private/tmp/astrid-registry-source-nohash.nSwcxz/projects/.astrid/media/sha256/b1/ff/b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640",
      "type": "image"
    }
  }
}
```

Notably, the canonical entry had no redundant `content_sha256` property; the
digest existed only in the standard managed locator. Source visualization and
render succeeded. Public `backup create` and `backup restore` copied it from:

- source: `/tmp/astrid-registry-source-nohash.nSwcxz/projects`
- backup: `/tmp/astrid-registry-backup-nohash.uZKngI/portable-backup`
- first restored root: `/tmp/astrid-registry-restore-nohash.AyrEwV/projects`

On the restored root, the unmodified command:

```text
python3 -m astrid timelines render main \
  --project portable --expected-version 2 \
  --output-name restored-before-fix.mp4 --json
```

failed with exit 1. The renderer reported that `hero`'s old absolute source
locator was outside the restored project root and was not an owned managed
media locator. This reproduced the acceptance finding without a programmatic
test or internal repository call.

An otherwise identical live registry that explicitly included
`content_sha256` already rendered after restore. That comparison isolated the
eligibility mismatch before the implementation was inspected.

## Exact cause

Canonical render already materializes a derived timeline snapshot and keeps
the immutable registry hash separate from a destination-local materialized
registry hash. Its managed-media resolver also already had the correct strong
ownership gate.

The narrow defect was one predicate before that gate: a stale registry entry
was considered for rebasing only when it carried an explicit
`content_sha256`, `sha256`, or `hash`. A normal absolute Astrid CAS locator
already contains the content digest as
`.astrid/media/sha256/aa/bb/<64-hex-digest>`, but that encoded identity was not
eligible. The entry therefore passed unchanged to asset authorization, which
correctly rejected the old-root absolute path.

## Product correction and safety boundary

Read-time registry materialization can now derive a candidate digest from the
locator only when the locator has the complete, absolute Astrid CAS shape:

```text
.../.astrid/media/sha256/<digest[0:2]>/<digest[2:4]>/<64 lowercase hex digest>
```

The derivation rejects relative paths, `..`, malformed fan-out directories,
and invalid digests. If an explicit registry hash is present, it must exactly
match the locator digest.

The old locator is only a content-identity hint. It is never authorized or
opened. Rebinding occurs only after all existing destination-side proofs pass:

1. the restored kernel has a media row with the exact digest owned by the
   requested project id or slug;
2. every matching `managed_local` location equals the current root's canonical
   CAS locator;
3. that destination locator is a regular, non-symlink file; and
4. hashing its current bytes produces the exact digest.

Wrong-project rows, arbitrary foreign paths, malformed managed-looking paths,
mismatched explicit hashes, missing files, symlinks, conflicting locations,
and tampered bytes all fail closed. The correction changes only a deep-copied
materialized registry. It does not update the database, timeline events,
history snapshots, command receipts, or the canonical registry hash.

## Fresh public-CLI acceptance replay

After the correction, the same portable backup was restored through the
public gateway into a second fresh root:

```text
python3 -m astrid backup restore \
  /tmp/astrid-registry-backup-nohash.uZKngI/portable-backup \
  --projects-root /tmp/astrid-registry-postfix.DSzlqR/projects

ASTRID_PROJECTS_ROOT=/tmp/astrid-registry-postfix.DSzlqR/projects \
  python3 -m astrid timelines show main --project portable --json

ASTRID_PROJECTS_ROOT=/tmp/astrid-registry-postfix.DSzlqR/projects \
  python3 -m astrid timelines visualize main \
  --project portable --format all --json

ASTRID_PROJECTS_ROOT=/tmp/astrid-registry-postfix.DSzlqR/projects \
  python3 -m astrid timelines render main \
  --project portable --expected-version 2 \
  --output-name immediate-restored.mp4 --json
```

Observed:

- restore completed with three media files and one project workspace;
- immediate visualization succeeded and durably registered its manifest and
  page/index artifacts;
- immediate canonical Remotion render succeeded as run
  `70a7d16188da7742e84349a2cf`, task
  `834d227faf5ecc705521b96208`;
- the primary MP4 was 47,728 bytes with SHA-256
  `336f6e28e01ea9ebfb0772e578cf185697b914e1913cd3bce810550bf17cb458`;
- `runs show --evidence --project portable` recorded `authority: kernel`,
  `config_version: 2`, canonical registry hash
  `2d887fc429af87a8dce3e29b0ea8e08641422f1836fbac91c11e3a1ba44c92bd`,
  and destination-local materialized registry hash
  `dbb9f70f5b7ae81409e4d122bfc03347ba88c7862cfa8c35be23e4fce8d76db9`;
- a second `timelines show` after render still returned version 2 and the
  original source-root locator, proving there was no hidden CAS save or
  immutable-history repair;
- `doctor` was fully green, including managed locators, SQLite quick check,
  foreign keys, and all four schema versions.

The source and restored locators differ, while timeline UUID, ULID, slug,
version, config hash, head event, head hash, and canonical registry hash remain
stable. Only the derived materialized registry is root-local.

## Narrow regression coverage

`tests/core/io/test_managed_media_resolver.py` now covers:

- a hash-less stale managed locator rebased after backup/restore;
- malformed fan-out and wrong-project managed-looking paths rejected;
- destination bytes changed after restore rejected;
- the existing explicit-hash restore path and non-managed foreign path cases.

Focused verification:

```text
pytest -q \
  tests/core/io/test_managed_media_resolver.py \
  tests/core/rendering/test_assets.py \
  tests/core/timeline/test_timeline_resolution.py \
  tests/packs/rendering/test_managed_timeline_render.py
```

Result: **60 passed in 7.07s**. Ruff on the resolver and its regression file
also passed. No gateway family, CLI surface, backup format, or immutable
timeline write path changed.

## Follow-up: restored visualization used a weaker resolver (2026-08-24)

The independent live replay in
`waves/replay-timeline-registry-restore-portability-2.md` exposed a second
surface-specific gap: canonical render rebased the hash-less old-root CAS
locator, but `timelines visualize` classified that same entry as
`unsupported` and emitted `MEDIA_MISSING` plus `UNSUPPORTED_MEDIA`. The
visualizer's classifier only called the managed resolver when an explicit
registry hash was present; it did not treat the strict CAS locator as a
content-identity hint. Snapshot media hashing had the same omission.

The fix is now shared by visualization and evidence acquisition. An exact
absolute `.astrid/media/sha256/aa/bb/<digest>` locator can supply a candidate
digest, but authorization still requires the active project's managed-media
row, canonical destination locator, regular non-symlink file, and current
byte hash. Foreign, malformed, arbitrary, and tampered paths remain rejected;
the canonical registry and history are never rewritten. The digest helper is
public only as an identity parser, not an authorization mechanism.

Fresh public-CLI replay used the existing self-contained backup restored into:

`/tmp/astrid-viz-restore-fixed-pnyQYw`

Immediately after restore, without timeline save/repair:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-viz-restore-fixed-pnyQYw \
  python3 -m astrid timelines visualize primary --project portable-maker \
  --format png,md --filmstrip off --out viz-fixed-live-2 --json
```

The command succeeded and its durable `asset-index.json` classified the
asset as `verified_original`, with the destination CAS path and expected and
observed hash
`b2b2356b1fa0d6b3d78fb6f06104232e17be829996e9f19b617bf214a263093c`. Its
diagnostics contain only the pre-existing `KERNEL_AUTHORITY` and
`SHOT_GROUPS_ABSENT` warnings: no `MEDIA_MISSING`, `UNSUPPORTED_MEDIA`, or
hash-mismatch warning. The same fresh root then passed the pinned Remotion
render (`restored-portable-followup.mp4`, output hash
`262a78f47ea79ef0737de8c51a0f32138043fbc622ea3a95c491863d9eebef56`).

Narrow verification now passes:

```text
pytest -q tests/core/timeline/test_timeline_resolution.py \
  tests/core/io/test_managed_media_resolver.py
30 passed in 0.66s
```

The new timeline guard proves a hash-less owned managed locator is verified
after restore, while the same locator is unsupported for a foreign project or
after its destination bytes are tampered.
