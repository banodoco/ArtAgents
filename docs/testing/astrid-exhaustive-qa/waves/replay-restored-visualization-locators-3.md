# Replay 3: restored visualization registry locators

Date: 2026-08-24  
Method: independent black-box live replay; public Astrid CLI only; no SDK,
source inspection, test suite, database editing, timeline save after restore, or
product edits

## Verdict

**PASS.** A canonical version-1 timeline whose stored registry contained an
absolute source-root managed-CAS locator and no explicit content hash survived
backup/restore into a different projects root. Immediately after restore,
without a timeline save:

- visualization resolved the asset to the destination CAS;
- `asset-index.json` reported `verified_original`;
- expected and observed SHA-256 both matched the imported media digest;
- diagnostics contained no `MEDIA_MISSING`, `UNSUPPORTED_MEDIA`, or hash
  warning for the restored timeline;
- a version-pinned canonical render succeeded and provenance pinned the kernel
  timeline ID, version 1, canonical head, config hash, stored-registry hash,
  and materialized-registry hash;
- `show` and `history` remained at version 1 and retained the original
  source-root locator byte-for-byte.

The source root remained present and readable throughout the replay. Resolving
the destination locator therefore demonstrated explicit restored-media
authority, rather than succeeding only because the old file had disappeared.

## Fresh roots and fixture

```text
source root:      /private/tmp/astrid-restore-src.rph82H
destination root: /private/tmp/astrid-restore-dst.gWcmAP
fixture root:     /private/tmp/astrid-restore-fixture.fKeJj1
backup:           /private/tmp/astrid-restore-backup.8qeE4I
project:          restore-lab
timeline:         main
```

A valid two-second H.264 fixture was created outside Astrid, then all Astrid
state was created through the public gateway:

```bash
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i color=c=blue:s=320x180:r=30:d=2 \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
  /private/tmp/astrid-restore-fixture.fKeJj1/source-blue.mp4

ffprobe -v error \
  -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate \
  -of json /private/tmp/astrid-restore-fixture.fKeJj1/source-blue.mp4
shasum -a 256 /private/tmp/astrid-restore-fixture.fKeJj1/source-blue.mp4
```

Observed fixture identity:

```json
{
  "codec_name":"h264",
  "width":320,
  "height":180,
  "r_frame_rate":"30/1",
  "duration":"2.000000",
  "size":"3268"
}
```

```text
1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b
```

## Source project and managed media

```bash
export ASTRID_PROJECTS_ROOT=/private/tmp/astrid-restore-src.rph82H
python3 -m astrid projects create restore-lab \
  --name 'Restore Registry Lab' --json
python3 -m astrid media import \
  /private/tmp/astrid-restore-fixture.fKeJj1/source-blue.mp4 \
  --project restore-lab --realm managed_local --json
python3 -m astrid media list --project restore-lab --json
```

The public import returned:

```json
{
  "id":"71786ec5-37b2-56ad-bf62-35a187dcc0ee",
  "content_hash":"1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
  "byte_size":3268,
  "media_kind":"video",
  "locations":[{
    "realm":"managed_local",
    "locator":"/private/tmp/astrid-restore-src.rph82H/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b"
  }]
}
```

## Canonical timeline with locator-only registry entry

The timeline was created with one ordinary video clip and a registry entry
whose `file` was the absolute source CAS locator. The registry deliberately
omitted `content_sha256`:

```bash
python3 -m astrid timelines create main --project restore-lab \
  --name 'Restorable Main' --default \
  --config '{"tracks":[{"id":"source","kind":"visual","label":"Source"}],"clips":[{"id":"src-video","at":0,"track":"source","clipType":"video","asset":"source-video","from":0,"to":2}],"output":{"resolution":"320x180","fps":30,"file":"restored.mp4"}}' \
  --registry '{"assets":{"source-video":{"file":"/private/tmp/astrid-restore-src.rph82H/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b","type":"video","duration":2}}}' \
  --json
python3 -m astrid timelines show main --project restore-lab --json
python3 -m astrid timelines history main --project restore-lab --json
```

Source state was:

```json
{
  "config_version":1,
  "timeline_id":"96c1f982-dcee-53b8-9f15-6f6e1f234aa9",
  "timeline_ulid":"payf8epas0vbvr8487r332ad1e",
  "slug":"main",
  "registry":{"assets":{"source-video":{
    "duration":2,
    "file":"/private/tmp/astrid-restore-src.rph82H/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
    "type":"video"
  }}}
}
```

History contained exactly `timeline.created`, version 1.

## Backup and cross-root restore

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-restore-src.rph82H \
  python3 -m astrid backup create \
  --out /private/tmp/astrid-restore-backup.8qeE4I

ASTRID_PROJECTS_ROOT=/private/tmp/astrid-restore-dst.gWcmAP \
  python3 -m astrid backup restore \
  /private/tmp/astrid-restore-backup.8qeE4I
```

Observed output:

```text
backup created at /private/tmp/astrid-restore-backup.8qeE4I
  media files: 1
  sqlite pages: 87

restore complete: /private/tmp/astrid-restore-dst.gWcmAP/.astrid/astrid.sqlite3
  restored media files: 1
  restored project workspaces: 1
```

The destination media row kept the same media ID and digest but was correctly
rebased:

```json
{
  "id":"71786ec5-37b2-56ad-bf62-35a187dcc0ee",
  "content_hash":"1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
  "locations":[{
    "realm":"managed_local",
    "locator":"/private/tmp/astrid-restore-dst.gWcmAP/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b"
  }]
}
```

`doctor --json` was fully green: paths, managed locators, SQLite quick check,
foreign keys, and all schema versions passed.

## Stored timeline remained immutable

Before visualization or render, and without any save:

```bash
export ASTRID_PROJECTS_ROOT=/private/tmp/astrid-restore-dst.gWcmAP
python3 -m astrid timelines show main --project restore-lab --json
python3 -m astrid timelines history main --project restore-lab --json
```

`show` still returned `config_version: 1` and the **old source-root locator**:

```text
/private/tmp/astrid-restore-src.rph82H/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b
```

History still contained one event only:

```json
[{"kind":"timeline.created","version":1}]
```

This establishes that restore did not rewrite authored timeline history.

## Immediate visualization without save

```bash
python3 -m astrid timelines visualize main --project restore-lab \
  --format md --filmstrip assets --json
```

The public command succeeded as run `5e4d57f8e3794d386ad4b76076`. Its
`asset-index.json` contained:

```json
{
  "canonical_ref":{
    "authored_id":"source-video",
    "kind":"asset",
    "timeline_uuid":"96c1f982-dcee-53b8-9f15-6f6e1f234aa9"
  },
  "contained_path":"/private/tmp/astrid-restore-dst.gWcmAP/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
  "expected_sha256":"1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
  "integrity_state":"verified_original",
  "observed_sha256":"1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b",
  "qualified_ref":"TL01.AS01",
  "role":"timeline_media"
}
```

This is the required read-time materialization behavior: the stored old-root
file value was not rewritten, while the frozen read model selected the exact
destination managed-media row and inferred the expected digest even though the
registry had no explicit hash.

The snapshot was pinned to canonical stream version 1 and the original create
event/hash:

```json
{
  "digest":"SNS:aa10a1a007e0a303cf541830dc171ba95ff11485104a85f3eefb52ba76488024",
  "event_head":{
    "last_hash":"8f68556a14f00c6d3ad793df68dc5d29d2caec56628821c99f56498b0885cd49",
    "version":1
  }
}
```

Diagnostics were exactly:

```json
[
  {
    "code":"KERNEL_AUTHORITY",
    "message":"visualization snapshot is pinned to stream version 1, event 777bc109b896422db1935458d693c608, hash 8f68556a14f00c6d3ad793df68dc5d29d2caec56628821c99f56498b0885cd49",
    "severity":"warning"
  },
  {
    "code":"SHOT_GROUPS_ABSENT",
    "message":"timeline has no pinnedShotGroups; shot scope is unavailable",
    "severity":"warning"
  }
]
```

There was no `MEDIA_MISSING`, `UNSUPPORTED_MEDIA`, hash mismatch, missing-hash,
or stale-locator warning. Asset filmstrip extraction also emitted frames,
confirming the destination video was readable as media rather than merely
present as bytes.

## Immediate version-pinned render without save

The first profile attempt used a natural nested structure:

```bash
python3 -m astrid timelines render main --project restore-lab \
  --expected-version 1 --backend rendering.remotion \
  --profile '{"video":{"codec":"h264","width":320,"height":180,"fps":30},"audio":{"codec":"aac"}}' \
  --output-name restored-v1.mp4 --json
```

It failed after admission because the protocol expects a flat profile with
additional required fields. Retrying with the documented default succeeded:

```bash
python3 -m astrid timelines render main --project restore-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name restored-v1.mp4 --json
```

Success identifiers:

```json
{
  "run_id":"cba7aae6c5aea0098b96be9c85",
  "kernel_task_id":"0e874b64f7a9fa8ee42c3e1919",
  "video_sha256":"c41c180fba3e94090678bb37a6593c2616801fba7d3c53e9ca7a6f123218a9d3",
  "provenance_sha256":"e14c6a0241fae27448111d2ce76944a178d003762071b08873b6d6182c28d25e"
}
```

The published file was a valid 2.048-second H.264/AAC MP4 at the default
1920x1080, 30 fps. Render provenance recorded:

```json
{
  "canonical_timeline":{
    "authority":"kernel",
    "config_version":1,
    "timeline_id":"96c1f982-dcee-53b8-9f15-6f6e1f234aa9",
    "timeline_slug":"main",
    "timeline_ulid":"payf8epas0vbvr8487r332ad1e",
    "head_event_id":"777bc109b896422db1935458d693c608",
    "head_hash":"8f68556a14f00c6d3ad793df68dc5d29d2caec56628821c99f56498b0885cd49",
    "config_hash":"3082222015dd04b77eccacf164d4344ddbc6cad6e938960dd90648868752c367",
    "registry_hash":"8320cbee8f1b3cb0cc28575e76b9c52e812406ee0195ae38f051590b6dd834ac",
    "materialized_registry_hash":"4a597021fad2c0d8a0b92316696b9ff2045e4a2f1620aab2630a6d62486c6ef8"
  }
}
```

A deliberately stale version pin failed before run/task admission:

```bash
python3 -m astrid timelines render main --project restore-lab \
  --expected-version 2 --backend rendering.remotion \
  --output-name stale-v2.mp4 --json
```

```json
{
  "data":null,
  "error":{
    "code":"validation_error",
    "details":{
      "kernel_run_id":null,
      "kernel_task_id":null,
      "run_id":null
    },
    "message":"stale timeline version: expected 2, current version is 1; show the timeline and retry with the current version"
  },
  "ok":false
}
```

## Destination media verification

```bash
python3 -m astrid media verify \
  71786ec5-37b2-56ad-bf62-35a187dcc0ee \
  --project restore-lab --realm managed_local --json
shasum -a 256 \
  /private/tmp/astrid-restore-dst.gWcmAP/.astrid/media/sha256/11/59/1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b
```

Both reported:

```text
1159a3b95cbf90a9550d6b25a0f269842115968254183b93453d1d759a1e0f5b
```

## Negative: foreign project managed locator

Using only public commands, a second project imported a distinct red video as
managed media. A draft timeline owned by `restore-lab` then referenced that
foreign project's exact global-CAS locator.

Visualization completed as evidence but did **not** treat the foreign bytes as
owned. Its asset index reported:

```json
{
  "contained_path":null,
  "expected_sha256":null,
  "integrity_state":"unsupported",
  "observed_sha256":null
}
```

Its diagnostics contained `MEDIA_MISSING` and `UNSUPPORTED_MEDIA` with:

```text
path escapes project root — local reference is not contained under project sources
```

The version-pinned render failed:

```json
{
  "ok":false,
  "error":{
    "code":"invocation_error",
    "message":"rendering.remotion does not support this render request: local assets are not renderable: Asset 'foreign-video' at /private/tmp/astrid-restore-dst.gWcmAP/.astrid/media/sha256/1d/23/1d235e244abcfed8d0b6ab6a3f47b484b454fd53dd7f3aef6304655e3cc67b40 is outside the allowed project root /private/tmp/astrid-restore-dst.gWcmAP/restore-lab and is not an owned managed media locator"
  }
}
```

This is the desired fail-closed ownership result. Visualization is a
diagnostic/evidence surface, so returning an evidence pack with explicit
unsupported state is more useful than aborting it. Render correctly refused
to consume the foreign bytes.

No managed-CAS bytes were deliberately tampered because doing so would be an
out-of-band mutation of Astrid-managed state, contrary to this public-CLI-only
replay. The foreign-owner negative covered the safe locator-admission branch.

## Friction

### P2 — `timelines render --profile` help does not reveal the profile schema

Help says only “Requested render profile as a JSON object.” A reasonable
nested video/audio mapping was accepted through CLI parsing, admitted as a
run, and then failed with ten missing flat protocol fields:

```text
container, duration_tolerance, fps_rational, height, pixel_format, time_base,
video_codec, video_level, video_profile, width
```

Suggested improvement: show a minimal complete example in `--help`, validate
the shape before run admission, or support the intuitive nested mapping. The
default profile path itself worked correctly.

### P3 — Visualization output is very noisy with repeated identical filmstrip frames

For the solid-color two-second source, 24 filmstrip labels all pointed to the
same deduplicated media ID/hash. Deduplication is correct, but the CLI JSON
envelope becomes difficult to scan. A compact artifact grouping/count would
improve live agent ergonomics while preserving the full machine payload.

## Final acceptance matrix

| Requirement | Result |
| --- | --- |
| Fresh source and destination roots | Pass |
| Valid managed video | Pass |
| Stored registry uses absolute source CAS | Pass |
| Stored registry omits explicit content hash | Pass |
| Backup/restore cross-root | Pass |
| No post-restore timeline save | Pass |
| `show` version remains 1 | Pass |
| `history` remains original version 1 | Pass |
| Stored old-root locator remains unchanged | Pass |
| Visualization selects destination CAS | Pass |
| `verified_original` | Pass |
| Expected/observed digest match | Pass |
| No missing/unsupported/hash warnings on restored timeline | Pass |
| Asset filmstrip reads destination media | Pass |
| Version-pinned render succeeds | Pass |
| Render provenance pins canonical identity/version/head/hashes | Pass |
| Stale version rejected before admission | Pass |
| Foreign managed locator not treated as owned | Pass |
| Foreign render rejected | Pass |

The restored registry behavior is ready from the perspective of this live
maker journey.
