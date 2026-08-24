# Replay: canonical render follow-up 3

Date: 2026-08-24

Mode: independent black-box live agent usage. I used only the public Astrid
skill, CLI help, product CLI commands, and `ffmpeg`/`ffprobe` for disposable
maker fixtures and output inspection. I did not inspect source or tests and did
not edit product code.

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-canonical-render-replay3.Bc8LsT/projects`

## Verdict

PASS for the just-fixed canonical-render contracts:

- explicit `clipType: "video"` completed create, managed visualization, and a
  real canonical Remotion render;
- a fresh `timelines render ... --json` emitted exactly one five-key JSON
  envelope on one stdout line, with no transient `.staging` path;
- the returned primary artifact and provenance sidecar were durable managed
  CAS media;
- the authoritative theme canvas produced 320x180 at 30 fps despite a
  deliberately conflicting legacy `output` hint of 640x360 at 24 fps;
- provenance pinned the exact canonical kernel identity and event head;
- exact replay returned the same run, task, and complete two-artifact set;
- `clipType: "image"`, `"audio"`, and `"media"` also rendered successfully,
  with no unregistered-type failure.

One separate P1 agent-feedback issue surfaced during the optional alias
expansion: a partial `output` object is accepted into the canonical timeline,
then rejected only after render admission, while the top-level render response
hides the actionable schema error. It does not invalidate the alias fix, but
it creates avoidable failed runs and recovery friction.

## Fresh setup

Created project:

- slug: `replay3`
- project id: `68f91641-6073-5a7b-b55c-ff7b5d341fce`

Created three local one-second fixtures and imported all into
`managed_local`:

| Kind | Content hash | Managed media id |
| --- | --- | --- |
| H.264/AAC video, 320x180 | `0e3933d7fd1af14471e01351b3dddcd521131cb790cc8d020488b08b16048dd6` | `d1169c28-690c-5af7-a47e-77a53d421867` |
| PNG image, 320x180 | `e443a44449fe52d02ddec85de45f6f24a747b0ff9f9bfed116bec3eb13b5ea4c` | `3dd5b192-ad92-5460-a41c-b40538a0a32f` |
| PCM WAV audio | `0b9ad6eee10065ce4b6975eba432f6a93839b780876da4ee973b0a82c9902817` | `2a0b6c35-c9ed-5ba9-8289-ad7e5152be46` |

Every import returned one exact successful JSON envelope and a managed CAS
locator.

## Primary video-alias timeline

Created default timeline `video`, version 1:

- timeline id: `08717f8a-898f-5a6b-bc26-d1884d6a5b42`
- timeline ULID: `x4mmd7jqpnnxb98c710w3pbkgw`

The relevant clip was:

```json
{
  "id": "video-source",
  "at": 0,
  "track": "source",
  "clipType": "video",
  "asset": "video-source",
  "from": 0,
  "to": 1
}
```

The same config declared:

```json
{
  "theme_overrides": {
    "visual": {"canvas": {"width": 320, "height": 180, "fps": 30}}
  },
  "output": {
    "resolution": "640x360",
    "fps": 24,
    "file": "conflicting-hint.mp4"
  }
}
```

Thus the legacy output hint intentionally conflicted with the explicit theme
canvas.

Before rendering, the public managed visualization succeeded:

```bash
python3 -m astrid timelines visualize video \
  --project replay3 --format md --filmstrip off --json
```

- kernel run: `44aa0f49486eb0edb120324bdd`
- returned artifacts: 11

This confirms create and visualization accepted the same explicit video clip
that was then sent to rendering.

## Fresh render stdout proof

Command:

```bash
python3 -m astrid timelines render video \
  --project replay3 --expected-version 1 \
  --output-name replay3-video.mp4 --json
```

Stdout was piped directly to a strict parser that:

1. read all stdout bytes;
2. called `json.loads` on the complete stream;
3. asserted the top-level keys were exactly
   `ok`, `data`, `error`, `receipt`, and `idempotency_key`;
4. asserted the raw stream contained no `.staging` text;
5. counted non-empty physical lines.

Result:

```json
{
  "strict_single_document": true,
  "exact_five_key_envelope": true,
  "contains_staging_path": false,
  "stdout_nonempty_lines": 1,
  "ok": true,
  "run": "50110fe9a94158d05c2aeda36c",
  "task": "93d4afb9938ec649f87cfdf167"
}
```

This is stronger than merely observing a successful command: any prefixed
path, suffixed second document, or non-JSON progress line would have made the
strict parse fail.

Returned durable artifacts:

| Role | Hash | Label |
| --- | --- | --- |
| Primary video | `b3b257cd0b3d0097726a3d086e78fe1444aadc0235f61916daeca050a4d5240c` | `replay3-video.mp4` |
| Provenance | `319fce7516c403eb2735dc2498077a976f3e0d9a2ceb7625939dec64c953eb12` | `replay3-video.mp4.provenance.json` |

Both returned `path` fields were under the durable managed
`.astrid/media/sha256/...` CAS tree, not the private staging tree.

## Media and authority proof

`ffprobe` reported:

- video: H.264, 320x180, 30/1 fps;
- audio: AAC;
- duration: 1.045333 seconds.

The actual 320x180 at 30 fps output follows the theme canvas and demonstrably
does not follow the conflicting legacy 640x360 at 24 fps hint.

The durable provenance's `output` points directly to the durable video CAS
path. Its canonical authority block contained:

```json
{
  "authority": "kernel",
  "project_id": "68f91641-6073-5a7b-b55c-ff7b5d341fce",
  "project_slug": "replay3",
  "timeline_id": "08717f8a-898f-5a6b-bc26-d1884d6a5b42",
  "timeline_ulid": "x4mmd7jqpnnxb98c710w3pbkgw",
  "timeline_slug": "video",
  "config_version": 1,
  "config_hash": "002d21fa54098f1f6e53af2dc2e9f4b5bb0d2b6665ded3fcff5b1ac0798debe7",
  "head_event_id": "6d671c6ab6d9476e81607802d711fe1c",
  "head_hash": "323e4a36742e86a3629b98e448b1a3c85777cc1a11b4948bd74b55f4a9467128",
  "registry_hash": "6a0528f8f1f442f9402fb0d61d5e8341fba11bd3c171409fc69d427c704d19ac",
  "materialized_registry_hash": "6a0528f8f1f442f9402fb0d61d5e8341fba11bd3c171409fc69d427c704d19ac"
}
```

`timelines show video` independently returned the same timeline identifiers,
version 1, explicit video clip, theme canvas, and conflicting output hint.

## Exact replay

Repeating the identical render command again passed the strict one-document
parser and returned:

```json
{
  "run": "50110fe9a94158d05c2aeda36c",
  "task": "93d4afb9938ec649f87cfdf167",
  "artifact_count": 2,
  "artifact_hashes": [
    "b3b257cd0b3d0097726a3d086e78fe1444aadc0235f61916daeca050a4d5240c",
    "319fce7516c403eb2735dc2498077a976f3e0d9a2ceb7625939dec64c953eb12"
  ],
  "artifact_roles": ["result", "output"]
}
```

The run, task, artifact count, ordering, roles, and hashes exactly match the
fresh render. Replay did not collapse the result to an empty artifact list.

## Image, media, and audio aliases

Created three additional canonical timelines backed by matching managed
media:

- `image`: `clipType: "image"`, PNG asset on a visual track;
- `media`: `clipType: "media"`, PNG asset on a visual track;
- `audio`: `clipType: "audio"`, WAV asset on an audio track plus a one-second
  text visual.

After completing each output object's required three fields, all rendered:

| Alias | Kernel run | Status | Artifacts | Primary video hash |
| --- | --- | --- | ---: | --- |
| `image` | `4293e7c03057a83395689cbf51` | succeeded | 2 | `451b043fc6ff845933b887db9107ec2158764de0f03fa738dbacfd9d0b2826b0` |
| `media` | `ff51a8bd8d865d13a0e2364ab2` | succeeded | 2 | `451b043fc6ff845933b887db9107ec2158764de0f03fa738dbacfd9d0b2826b0` |
| `audio` | `1f52022cf4e1fe3fbceda48dd2` | succeeded | 2 | `81bddcea44c66e802222a8699c8f4e9487ab482c118330de47f4288b806a6bc6` |

Every success parsed as one JSON document and contained no staging path. The
image/media outputs were byte-identical, as expected for the same PNG and
canvas; the provenance differed because canonical timeline identity differed.
The audio result and the shared image/media result both probed as playable
H.264/AAC, 320x180, 1.045333-second MP4s.

None of these runs reported an unregistered clip type.

## Friction and new finding

### P1: malformed render config is admitted and its actionable error is hidden

My first optional alias timelines set `output` to only `{"file":"...mp4"}`.
Canonical create accepted each as version 1. `timelines render` then admitted
three kernel runs and returned only the generic top-level message:

`timeline render failed`

The response did contain run/task/attempt ids, but not the real cause. Only a
second public command, `runs show <run> --evidence`, revealed the actionable
failure:

```text
timeline is not renderable: 'resolution' is a required property
... required: ['resolution', 'fps', 'file']
```

Failed runs:

- image: `33f7ee4ba3f13319a976801236`
- media: `84fc2baf148888c30885582e6b`
- audio: `84770a7f9c1ea731d317314bb2`

This was unrelated to clip-type support. A public CAS save adding
`resolution` and `fps` advanced each timeline to version 2; all three then
rendered successfully.

The friction is still material for agents:

- a purely local schema problem creates durable failed runs instead of failing
  before admission;
- the command that fails does not explain how to repair the request;
- the error becomes understandable only if the agent knows to inspect run
  evidence using a returned id.

Smallest durable improvement: preflight the materialized canonical timeline's
render schema before run admission. If that is intentionally deferred, bubble
the structured child failure message into the `timelines render` error
envelope so recovery does not require a second diagnostic journey.

## Final agent-UX assessment

The targeted follow-up is genuinely fixed. The primary video path is clear,
machine-safe, durable, correctly sized, authority-pinned, and replay-stable.
All advertised built-in media aliases work through real rendering. The only
remaining friction found in this wave concerns preflight/error propagation
for a separate malformed-output case, not the clip aliases or stdout fix.
