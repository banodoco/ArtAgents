# Live timeline authority audit — wave 1

Date: 2026-08-24 (Europe/Berlin)  
Scope: black-box public CLI/SDK/help/docs only. No source, tests, SQLite, or prior QA reports were inspected.  
Disposable roots: `/tmp/astrid-live-timeline-authority-UEL1ug`, backup `/tmp/astrid-live-timeline-authority-backup-xHjtdH`, restored root `/tmp/astrid-live-timeline-authority-restored-x49SFI`.

## Verdict

**Timeline authority: PASS (kernel current snapshot + append-only timeline version history).** Public `timelines show`, `history`, `diff`, archive/unarchive, and backup/restore all read the kernel timeline, not a required filesystem timeline file. A stale CAS save is rejected without a timeline event. v1 remains immutable in history and its render/provenance artifacts remain in managed media after v2.

**Consumer provenance: PARTIAL/GAP.** Visualization ground-truth identifies the timeline UUID/ULID and current content (including `AUTHORITY V2`), but its `event_head.version` is `2` while public `config_version` was `4` before archive; it is an event-stream/run snapshot version, not the timeline document version. Render provenance identifies the standalone timeline input path, timeline input hash, registry hash, request digest, renderer and output hash, but does **not** identify the kernel timeline UUID, config version, or a timeline config hash tied to `timelines show`.

**Restore: PASS with friction.** Database/media restore reproduced the current v2 timeline and all six timeline history entries. Backup restore did not recreate the ordinary project directory projection (`project.json` and `plan.md`), so a fresh visualization initially failed `project not found`; recreating those normal project metadata files allowed visualization to succeed and prove v2 current content. No timeline directory/file was needed by `timelines show`/history/diff or visualization after that repair.

## Exact journey and evidence

### Bootstrap and managed media

Commands (all with `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-timeline-authority-UEL1ug`):

```text
python3 -m astrid doctor --json
python3 -m astrid projects create authority-demo --name 'Live Timeline Authority Audit' --json
python3 -m astrid projects select authority-demo --json
python3 -m astrid projects current --json
```

The clean-root doctor failed only because the database/data directory did not yet exist, as documented. Project id: `a2085714-5e9c-5f62-a39a-4c3d4a32f00d`; project path: `/private/tmp/astrid-live-timeline-authority-UEL1ug/authority-demo`.

Three generated fixtures were imported with `media import --realm managed_local`:

| kind | media id | content hash | canonical managed locator |
|---|---|---|---|
| image/png | `fffb969a-7a90-56d8-b717-111c5becb11a` | `446f638b0ecb8afb85606f4636ea8234354892e025d70b086180f2f1736d32c1` | `.astrid/media/sha256/44/6f/446f638b0ecb8afb85606f4636ea8234354892e025d70b086180f2f1736d32c1` |
| video/mp4 | `576872bb-b305-50e7-8861-4de54c2ae27b` | `a4a131526a1e127e7f924006bb57329d3808743ac55e14eaf381143ea918d2e5` | `.astrid/media/sha256/a4/a1/a4a131526a1e127e7f924006bb57329d3808743ac55e14eaf381143ea918d2e5` |
| audio/x-wav | `36fedf32-6529-5515-9dae-f2cdca792d3d` | `10f1620c6dc645bc674de1466a32b2b6a7f006bdd3f0a99da2a092ee5a50efbe` | `.astrid/media/sha256/10/f1/10f1620c6dc645bc674de1466a32b2b6a7f006bdd3f0a99da2a092ee5a50efbe` |

### v1 create, show/history/diff, visualize, render

Created default slug `primary` with visible text `AUTHORITY V1`, image/video/audio media clips, and the three managed canonical locators in the registry. Timeline identity:

```text
timeline_id   bcc600b9-3491-555f-bd43-f1a9833cebb8
timeline_ulid dvw9a5qj5pqh7zsvxdv1zhbent
config_version 1
```

Immediately after create:

- `timelines show primary --json` returned the full v1 config and registry, with `config_version: 1`.
- `timelines history primary --json` returned exactly one `timeline.created`, `version: 1`.
- `timelines diff primary --json` returned `[]`.

`timelines visualize --timeline-slug primary --format all --layout both --filmstrip assets --json` succeeded as run `ab50d79705ea444e505e12b262`, task `d859c4ccbfbf0f2190f477891c`, primary manifest media hash `ef4f02d887095ad3a413ac21d375cc86c1d5da5420e28ce05f42265e4b65bdd0` and ground-truth hash `5c3a8650db12f324f95cf2e3c59d222eda3f4629783360f5edcdfd0b8e9ff337`. It identified the timeline UUID/ULID and clips, but warned that absolute managed locators were `MEDIA_MISSING`/`UNSUPPORTED_MEDIA` to the visualizer's legacy local-path inspector (`path escapes project root`). This is a visualizer media-provenance gap; the kernel media rows were healthy and the render path accepted the same canonical managed bytes.

Rendered through the public SDK boundary:

```python
sdk.invoke("rendering.render", kind="executor", project="authority-demo", inputs={
  "timeline": "authority-demo/render-inputs/authority-v1.timeline.json",
  "assets_registry": "authority-demo/render-inputs/authority-v1.assets.json",
  "backend": "rendering.remotion", "output_name": "authority-v1.mp4"
})
```

Render run `fed1e1d54ca40787c839c182b4`, task `fe4eee0f77a1c6a57a3bbc6983`, succeeded. Public `runs show --evidence` returned:

```text
authority-v1.mp4 content_hash 15a1d997f31c26aabc5f71da176398ef7f3c997c8b0dab16fe56f755ee39ee87
authority-v1.mp4.provenance.json content_hash 4703ec4182327ea8786b1dd7041095e756450984d87f0e53ba667e4c7620b831
```

The v1 sidecar recorded timeline input hash `75b65472ba5b090b2ce280ae6a9a9cd8606753d2905214e67a193089930a6054`, registry hash `ba19303a14df34957b4b8b5ce14553a7f29c6c3511c6e3f4aece1b3e1b70cf18`, request digest `52959dc6e7a3d54f026682fa4d949276e13e0b3403e1ac0fdd4fd8096514dcb7`, and `rendering.remotion` support/provenance. It did not include the kernel timeline id/version.

### v2 CAS, stale recovery, and consumers

v2 changed visible title to `AUTHORITY V2`, image hold from 2s to 1s, video/audio timing to 3s, visual-track label, output name, and registry metadata. Save with `--expected-version 1 --idempotency-key save-v2` succeeded as `config_version: 2` and event `9c2ede25d25e4e388990802f7c7d42d4`.

Deliberate stale save with the same document and `--expected-version 1 --idempotency-key stale-v1` exited 1:

```json
{"code":"stale_version","details":{"current_version":2,"expected_version":1},"message":"... no write occurred ..."}
```

Recovery save using current expected version 2 succeeded as `config_version: 3`; a valid registry update (generation ids) then saved as `config_version: 4`. `timelines history` and `diff` showed exactly four document events before archive: create v1, save v2, save v3, save v4. The stale attempt produced no timeline event. Diff was coherent: v1→v2 changed `clips`, `output`, `tracks` and registry asset fields; v2→v3 was unchanged (recovery save); v3→v4 changed `audio`, `image`, `video` registry fields.

The first v2 render attempt deliberately exposed a registry validation failure (`unknown key 'label'`) and produced a failed run, but no timeline mutation. After replacing that unsupported registry key with documented-style `generationId` fields, v2 rendered successfully as run `638162ad803963b9ae11f0eaf4`, task `996f586abae70b4ecc3512084c`, with managed outputs:

```text
authority-v2-success.mp4 content_hash 2f2594bf90ac3976d1dd114d8452085af9cd289b58138248174e9df757c3513b
authority-v2-success.mp4.provenance.json content_hash aa7dd16185f27f65d899f73263c11ef1b053d127892c31c6c6b23cedf811f966
```

The v2 sidecar recorded timeline input hash `6d40c6d84523addf0e069b1caee0a9255886e961a6d2860574a4d35d9b72d8fd`, registry input hash `d95f0091bee926c280be9e083eecaa57a1d95d7c0a7f5c9bd246ebcb768372b0`, request digest `30d359ab66ad3b1a6704d85f77c5c20d363afc8f554bd901e9692eff1b788251`, and output hash `2f2594...`; it still did not identify timeline UUID/config version.

Two distinct fresh visualization requests both consumed v2 current state:

| request | run/task | manifest hash | ground-truth hash | SNS digest | event_head.version | visible evidence |
|---|---|---|---|---|---:|---|
| `--format md --layout linear` | `3c395d9b5574ee2fc7efcabcf7` / `3cd2985e128b4bbd070741a570` | `f1f8bb259aafe0b901a91f455b28c9168df40e2794c1de1bded119eabe2a917f` | `aa7706b3fc2766e15a55187a137407547c5d54fb15d1844b89f6412f19963ccc` | `SNS:7731b8147265c801bc883dc54dabf4d7e16270eee9222b9b5685d901e5078a99` | 2 | `AUTHORITY V2`, image 1s, video/audio 3s |
| `--format svg --layout time-scaled` | `92023ede6844c7d26facfbbde9` / `39a73239b37ac2769e99be6f81` | `14ba1ac24aa65bc3f6a66b23bca8ecbcfd86fa2782e90756ab30a107c77573ef` | `2e7e5795a43d273a2015fc804d05ec9113e8048bcfc46ee4375a7b73ac78bb36` | `SNS:8d1ae0b820a5b244ecc6c01334a3bcf3b896410a3038459fc2b913c3a3d6ee34` | 2 | `AUTHORITY V2`, image 1s, video/audio 3s |

The SNS digests were **not equal** despite unchanged timeline content: each visualization appended a distinct run/task event head. Public `timelines show` remained `config_version: 4`. Thus the visualization event-head version is not the timeline document version.

Repeating the exact original `--format all` request returned the prior run id `ab50d79705ea444e505e12b262` and `outputs: {}` (idempotent replay), so changing a format/layout was required to force a fresh evidence pack.

### Archive/unarchive

`timelines archive primary --idempotency-key archive-v4` returned `config_version: 5`; active `timelines list` returned `[]`, while `--include-archived` returned the same slug/id. Archived `show` still exposed v2 config/title/registry. `timelines history` added exactly one `timeline.archived`, `version: 5`, with null config/registry.

`timelines unarchive primary --idempotency-key unarchive-v4` returned `changed: true`, `config_version: 6`; `show` restored the same v2 content and `history` added exactly one `timeline.unarchived`, `version: 6`. No v1 content was replaced or lost.

### Backup/restore

```text
backup created at /tmp/astrid-live-timeline-authority-backup-xHjtdH
  media files: 37
  sqlite pages: 168
restore complete: /private/tmp/astrid-live-timeline-authority-restored-x49SFI/.astrid/astrid.sqlite3
  restored media files: 37
```

On the restored root, `doctor --json` passed all required checks (`managed-media sha256 tree accessible`, `quick_check ok`, `no foreign key violations`, `core=1, references=1, shots=1, timeline=1`). `timelines show primary` returned the same timeline id/ULID, title `AUTHORITY V2`, timing, registry, and `config_version: 6`; `history` returned the same six entries (versions 1–6). Managed media ids/content hashes were preserved and locators were correctly rebased under the restored `.astrid/media` tree.

Restore friction: the restored root initially contained `.astrid` only; the normal project directory projection was absent. Consequently visualization returned `project not found: 'authority-demo'` even though public project/timeline reads worked. Recreating the ordinary `authority-demo/project.json` and `plan.md` projections (no timeline file) made the fresh visualization succeed:

```text
restored visualization run bf8881615d8fa0dc315b48def6
task 2a5013244195e600e6bdff0798
manifest hash d3af8d4d6c8ff708276fbbbd21e3174f7705354f84e88ab77f40bb15c3a8a5b8
ground-truth hash 8390e8c4cf31e212e8d501775d4e887bfb67a7d0dcff092bdbeb2916bc147bd7
SNS SNS:98341737044e554b7932529ce23330bd8ecc90b6255ec2e10cb5b7ad8e73c831
```

Its ground-truth contained the same timeline UUID/ULID, `AUTHORITY V2`, image 1s, and video/audio 3s, proving the new visualization used restored kernel current state. It repeated the expected absolute-locator warnings because the timeline registry stores the original managed locators; the restored media rows themselves had rebased locators. This is a clear restore/provenance gap for consumer registries, not evidence that a filesystem timeline is authoritative.

## Source of truth conclusion

Consumers used the **kernel current timeline snapshot** (`timelines show`, visualization ground truth, archive/unarchive, and restore), with the **kernel timeline version/event log** as the history authority. The filesystem render-input JSONs were explicitly supplied copies for the standalone rendering boundary; changing/removing a required timeline file would affect that render invocation, but no unexplained `<project>/timelines/...` file was needed for timeline CRUD, history, diff, or visualization. Run/task event streams recorded capability execution and output media, not timeline document versions. The main remaining gaps are explicit timeline identity/version/config-hash propagation into render provenance, unstable SNS across otherwise unchanged visualization requests, visualizer rejection of canonical managed locators, and restore omission of ordinary project projections plus stale absolute registry locators.
