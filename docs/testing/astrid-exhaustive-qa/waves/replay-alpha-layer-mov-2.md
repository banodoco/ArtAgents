# Replay 2: alpha-layer MOV correction

Date: 2026-08-24  
Method: independent black-box live agent replay using current public Astrid
documentation and SDK only; no source inspection, test suite, database edits,
or product edits  
Reference followed: `docs/reference/layer-stack.md`  
Disposable root: `/private/tmp/astrid-alpha-replay.o6BRBh`

## Verdict

**DIRECT SDK PASS; UNIFIED PROJECT ROUTE FAIL.**

The corrected renderer behavior is real through the exact direct public SDK
shown in `layer-stack.md`:

- a timeline stamped with `metadata.astrid_layer = {z: 1, alpha: true}`
  rendered successfully to `.mov`;
- `ffprobe` reported ProRes profile 4444, `ap4h`, and `yuva444p12le`;
- an extracted RGBA frame contained genuinely transparent, partially
  transparent, and fully opaque pixels;
- the MOV used stereo PCM S16LE audio as documented;
- the adjacent provenance sidecar declared MOV/ProRes/`yuva444p12le` and
  matched the published file hash;
- the equivalent unstamped `.mp4` remained opaque H.264/AAC;
- an unstamped `.mov` failed before renderer execution with an actionable
  `RendererProtocolError` and created neither output nor provenance.

However, the project-scoped public executor and canonical timeline product
route still impose an older unconditional `.mp4` restriction. Both stamped
and unstamped `.mov` requests were admitted as kernel runs and then failed
with `output_name must end with .mp4`. Therefore the fix is not end-to-end for
the full public product surface, and there is no project-managed durable MOV
or kernel-linked provenance for an alpha layer yet.

## Public fixture

A disposable project was created through the gateway:

```bash
alpha_root=$(mktemp -d /private/tmp/astrid-alpha-replay.XXXXXX)
ASTRID_PROJECTS_ROOT="$alpha_root" \
  python3 -m astrid projects create alpha-lab \
  --name 'Alpha Layer Lab' --json
```

Resulting project root:

```text
/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab
```

No media assets were needed. Two fresh timeline files were authored from the
public timeline schema and layer-stack contract.

### Stamped z>0 timeline

```json
{
  "metadata": {
    "astrid_layer": {
      "z": 1,
      "alpha": true
    }
  },
  "theme_overrides": {
    "visual": {
      "canvas": {
        "width": 320,
        "height": 180,
        "fps": 30
      }
    }
  },
  "tracks": [
    {
      "id": "overlay",
      "kind": "visual",
      "label": "Transparent overlay"
    }
  ],
  "clips": [
    {
      "id": "alpha-title",
      "at": 0,
      "track": "overlay",
      "clipType": "text",
      "hold": 1,
      "text": {
        "content": "ALPHA",
        "fontSize": 48,
        "color": "#ff3355",
        "align": "center"
      }
    }
  ],
  "output": {
    "resolution": "320x180",
    "fps": 30,
    "file": "stamped-alpha.mov"
  }
}
```

Path:

```text
/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/stamped-alpha.timeline.json
```

### Unstamped opaque control

The control used the same 320x180/30 fps canvas and one text clip, but had no
root `metadata.astrid_layer` and declared `unstamped-opaque.mp4`.

Path:

```text
/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/unstamped-opaque.timeline.json
```

## Stamped alpha MOV through the documented direct SDK

The public invocation matched the direct-use shape in `layer-stack.md`:

```python
from astrid.sdk.rendering import render

out = render(
    timeline_path="/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/stamped-alpha.timeline.json",
    assets_registry_path=None,
    out_path="/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/outputs/stamped-alpha.mov",
    backend="rendering.remotion",
)
print(out)
```

It returned:

```text
/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/outputs/stamped-alpha.mov
```

### Codec and profile evidence

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,time_base,codec_tag_string \
  -of json stamped-alpha.mov
```

Exact video stream result:

```json
{
  "codec_name":"prores",
  "profile":"4444",
  "codec_tag_string":"ap4h",
  "width":320,
  "height":180,
  "pix_fmt":"yuva444p12le",
  "r_frame_rate":"30/1",
  "time_base":"1/90000"
}
```

Audio stream:

```json
{
  "codec_name":"pcm_s16le",
  "sample_fmt":"s16",
  "sample_rate":"48000",
  "channel_layout":"stereo"
}
```

This matches the public contract: ProRes 4444 with an alpha plane in MOV, not
VP9, plus PCM audio.

### Pixel-level alpha evidence

The first frame was decoded to an RGBA PNG:

```bash
ffmpeg -hide_banner -loglevel error -i stamped-alpha.mov \
  -frames:v 1 -pix_fmt rgba stamped-alpha-frame.png
```

RGBA inspection reported:

```text
mode: RGBA
size: 320x180
alpha extrema: 0..255
transparent pixels: 46123
nonzero-alpha pixels: 11477
```

Concrete samples from that frame:

```text
transparent: (x=0,   y=0)  → RGBA (0,   0,  0,  0)
partial:     (x=167, y=29) → RGBA (0,   0,  0,  1)
opaque text: (x=110, y=42) → RGBA (255, 51, 85, 255)
```

This proves the file does not merely advertise an alpha-capable pixel format;
the rendered frame actually carries transparent background and opaque content.

### Direct SDK provenance

The SDK wrote:

```text
stamped-alpha.mov
stamped-alpha.mov.provenance.json
```

Published video SHA-256:

```text
87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44
```

Provenance contained:

```json
{
  "schema_version":2,
  "timeline":"/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/stamped-alpha.timeline.json",
  "output":"/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/outputs/stamped-alpha.mov",
  "sha256":"87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44",
  "engine":"rendering.remotion",
  "requested_policy":"rendering.remotion",
  "resolved_policy":{
    "planner":"astrid.direct",
    "renderers":["rendering.remotion"],
    "finalizer":"astrid.direct-finalizer"
  },
  "artifact_profile":{
    "container":"mov",
    "video_codec":"prores",
    "pixel_format":"yuva444p12le",
    "width":320,
    "height":180,
    "fps_rational":[30,1],
    "time_base":[1,90000],
    "audio_codec":"pcm_s16le",
    "audio_sample_rate":48000,
    "audio_channel_layout":"stereo"
  }
}
```

The sidecar hash agreed with the actual MOV.

## Unstamped opaque MP4 control

```python
from astrid.sdk.rendering import render

out = render(
    timeline_path="/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/unstamped-opaque.timeline.json",
    assets_registry_path=None,
    out_path="/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/outputs/unstamped-opaque.mp4",
    backend="rendering.remotion",
)
```

`ffprobe` reported:

```json
{
  "codec_name":"h264",
  "profile":"High",
  "codec_tag_string":"avc1",
  "width":320,
  "height":180,
  "pix_fmt":"yuvj420p",
  "r_frame_rate":"30/1",
  "time_base":"1/90000"
}
```

Audio was AAC, 48 kHz stereo. Decoding the first frame to RGBA produced:

```text
corner RGBA: (0, 0, 0, 255)
center RGBA: (0, 0, 0, 255)
alpha extrema: 255..255
```

Thus the unstamped/default path remains fully opaque. Its provenance declared
MP4/H.264/`yuv420p`/AAC and matched the actual published file hash:

```text
8ceb751cb5ffad9ad15ef1143db48ee17e2506273a8aaf759e25020dc0d3ffef
```

`ffprobe` spelling `yuvj420p` versus provenance's `yuv420p` reflects the
decoded full-range 4:2:0 variant; neither carries alpha.

## Unstamped MOV negative

The same unstamped timeline was sent to the direct public SDK with a `.mov`
destination:

```python
from astrid.sdk.rendering import render

render(
    timeline_path=".../unstamped-opaque.timeline.json",
    assets_registry_path=None,
    out_path=".../unstamped-invalid.mov",
    backend="rendering.remotion",
)
```

It failed immediately:

```text
RendererProtocolError: output_name must end in .mp4 for the selected render profile; got 'unstamped-invalid.mov'
```

Observed filesystem state:

```text
output exists: false
provenance exists: false
```

This is actionable and fail-closed before Remotion execution/publication. In
the direct SDK there is no kernel run admission, so this is the equivalent
pre-render validation boundary.

## Project-scoped route mismatch

Because the task requested durable/provenance inspection if a project route
was used, both project variants were also exercised.

### Raw project executor invocation

```python
import astrid.sdk as sdk

sdk.invoke(
    "rendering.render",
    kind="executor",
    include_installed=False,
    project="alpha-lab",
    inputs={
        "timeline":"/private/tmp/astrid-alpha-replay.o6BRBh/alpha-lab/inputs/stamped-alpha.timeline.json",
        "backend":"rendering.remotion",
        "output_name":"stamped-alpha.mov"
    }
)
```

Unexpected result:

```json
{
  "ok":false,
  "run_id":"6555d568501a5fcde65775fedb",
  "kernel_task_id":"6ae1c5b3f80779f691c4f67608",
  "error":{
    "type":"ValueError",
    "message":"output_name must end with .mp4, got 'stamped-alpha.mov'"
  }
}
```

The request was admitted and then rejected by an older unconditional executor
guard. No MOV or durable provenance artifact was published.

### Canonical timeline product route

The stamped and unstamped configs were each created as canonical version-1
timelines through `astrid timelines create`, then invoked with:

```bash
python3 -m astrid timelines render alpha-canonical \
  --project alpha-lab --expected-version 1 \
  --backend rendering.remotion --output-name canonical-alpha.mov --json

python3 -m astrid timelines render opaque-canonical \
  --project alpha-lab --expected-version 1 \
  --backend rendering.remotion --output-name invalid-opaque.mov --json
```

Both failed only after run admission:

```json
{
  "ok":false,
  "error":{
    "code":"invocation_error",
    "message":"output_name must end with .mp4, got 'canonical-alpha.mov'"
  },
  "details":{
    "run_id":"4f2575d4fa4b54b85192498326",
    "kernel_task_id":"f41e10590e8a687ce177740278"
  }
}
```

```json
{
  "ok":false,
  "error":{
    "code":"invocation_error",
    "message":"output_name must end with .mp4, got 'invalid-opaque.mov'"
  },
  "details":{
    "run_id":"d4a2ab91e9a4f55e7b74b609c9",
    "kernel_task_id":"144d64a25c23afbd3791468eea"
  }
}
```

The stamped case should have succeeded; the unstamped case should have been a
typed validation error with null run/task IDs and the more specific selected-
profile explanation used by the direct service. Neither occurred.

## Findings and friction

### P1 — Alpha MOV support is not propagated through project execution

The core/public direct service correctly distinguishes stamped alpha MOV from
ordinary output, but the project executor rejects all `.mov` names before
that logic can run. This blocks kernel-managed alpha artifacts, canonical
timeline rendering, durable media publication, and kernel-linked provenance.

Recommended correction: remove the executor's unconditional `.mp4` guard and
delegate suffix/profile validation to the shared render service. The managed
canonical preflight should apply the same stamp-aware validation before run
admission so unstamped `.mov` produces null run/task IDs.

### P2 — The layer-stack reference states the stamp but lacks a complete direct alpha example

The reference says the host stamps `metadata.astrid_layer.alpha` and gives the
`LayerRef` dataclass, but it does not show the minimal materialized timeline
JSON or a direct `.mov` call. A black-box agent must infer:

```json
{"metadata":{"astrid_layer":{"z":1,"alpha":true}}}
```

and pair it with `out_path="...mov"`. Add this as a small verification recipe,
including the expected ProRes/alpha `ffprobe` fields.

### P3 — Successful direct render leaves a zero-byte `.lock` sibling

After success, both direct outputs retained a zero-byte `<output>.lock` file.
This may be deliberate cross-process coordination, but the docs do not explain
whether it is durable state or safe cleanup. It adds minor output-directory
clutter and uncertainty for makers packaging results.

### P3 — Opaque provenance/ffprobe pixel-format spelling differs

Provenance declares `yuv420p`; local `ffprobe` reports `yuvj420p`. Both are
opaque H.264 4:2:0 and this did not affect the requested behavior, but exact
artifact-profile consumers may interpret the strings as a mismatch. If full
range is intentional, provenance could include color-range evidence.

## Acceptance matrix

| Requirement | Direct documented SDK | Project/canonical route |
| --- | --- | --- |
| z>0 + `astrid_layer.alpha:true` to `.mov` | Pass | **Fail** |
| ProRes 4444 | Pass | Not produced |
| `yuva444p12le` alpha plane | Pass | Not produced |
| RGBA transparent frame pixel | Pass | Not produced |
| Opaque unstamped `.mp4` | Pass | Existing MP4 route remains available |
| H.264/AAC opaque control | Pass | Not needed for correction replay |
| Unstamped `.mov` actionable rejection | Pass | Generic suffix error |
| Rejection before kernel admission | N/A (no kernel) | **Fail** |
| Adjacent provenance | Pass | No alpha artifact published |
| Kernel-managed/durable alpha artifact | N/A | **Fail** |

## Final assessment

The alpha-layer codec correction is technically correct at the public
rendering-service boundary and the produced pixels prove it. The remaining
work is a thin but important facade integration: project/canonical execution
must stop overriding the shared stamp-aware suffix contract. Until then,
alpha MOV is usable only via direct `astrid.render`, not as a fully managed
Astrid run.

## Post-fix managed replay — 2026-08-24

Status: **P1 resolved; managed/canonical alpha MOV now passes end to end.**

Fresh public root:

```text
/private/tmp/astrid-alpha-managed-fix.YLb6Pe
```

The project plus stamped and unstamped canonical version-1 timelines were
created with the same public `projects create` and `timelines create` commands
shown above. The stamped config retained the 320×180/30 fps text layer and
exact `metadata.astrid_layer={z:1,alpha:true}` contract.

### Unstamped MOV is rejected before admission

Exact command:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-alpha-managed-fix.YLb6Pe \
python3 -m astrid timelines render opaque \
  --project alpha-lab --expected-version 1 \
  --backend rendering.remotion --output-name invalid-opaque.mov --json
```

Exact output:

```json
{"data":null,"error":{"code":"validation_error","details":{"kernel_attempt_id":null,"kernel_run_id":null,"kernel_task_id":null,"run_id":null,"sdk_category":"validation","sdk_error":"CapabilityValidationError","validation":{"output_name":"invalid-opaque.mov","required_timeline_stamp":"metadata.astrid_layer.alpha=true"}},"message":"output_name 'invalid-opaque.mov' uses .mov, but the timeline is not stamped metadata.astrid_layer.alpha=true"},"idempotency_key":"","ok":false,"receipt":null}
```

`runs list --project alpha-lab --json` returned `data:[]` both before and
after. This is a genuine pre-admission rejection: no run, task, attempt,
snapshot, output, or provenance was created.

### Version-pinned canonical alpha MOV succeeds

Exact command:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-alpha-managed-fix.YLb6Pe \
python3 -m astrid timelines render alpha-layer \
  --project alpha-lab --expected-version 1 \
  --backend rendering.remotion --output-name canonical-alpha.mov --json
```

Key exact result fields:

```json
{
  "ok": true,
  "data": {
    "kernel_run_id": "5c7d0ddc5dd5f804933ee6b84c",
    "kernel_task_id": "3b8b8126847fab630e04a3704e",
    "kernel_attempt_id": "01m0spyz1tc9sp3f6tpgnzsqe4",
    "outputs": {
      "artifacts": [
        {
          "label": "canonical-alpha.mov",
          "requested_output_name": "canonical-alpha.mov",
          "media_id": "01m0spz54tew266mjs24gnzkyn",
          "content_hash": "87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44",
          "path": "/private/tmp/astrid-alpha-managed-fix.YLb6Pe/.astrid/media/sha256/87/ae/87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44"
        },
        {
          "label": "canonical-alpha.mov.provenance.json",
          "media_id": "01m0spz54ydy07p0pcqb5c7fqd",
          "content_hash": "66b06279631cf15f1af662c661d63184892a8f9adc66e093193e5f16c0316103"
        }
      ]
    }
  }
}
```

`media show 01m0spz54tew266mjs24gnzkyn --project alpha-lab --json`
reported `media_kind:"video"`, `mime_type:"video/quicktime"`, probe
`container:"mov"`, `decodable:true`, and
`rel_path:"out/canonical-alpha.mov"`.

Exact `ffprobe` facts from the suffixless durable CAS object:

```text
video: prores, profile 4444, tag ap4h, yuva444p12le, 320x180,
       30/1 fps, time_base 1/90000
audio: pcm_s16le, tag sowt, 48000 Hz, stereo
duration: 1.000000
```

One frame decoded to RGBA produced:

```text
mode=RGBA size=(320, 180)
alpha_extrema=(0, 255)
corner=(0, 0, 0, 0)
nonzero_alpha_pixels=11477
```

This proves the managed object contains transparent pixels, not merely an
alpha-capable codec declaration.

### Exact authority and durable provenance

The sidecar's `output` is the durable CAS locator above, its artifact SHA-256
is the same `87ae...fa44` digest, and its declared profile is MOV/ProRes/
`yuva444p12le`/PCM S16LE 48 kHz stereo. Its canonical authority is:

```json
{
  "authority": "kernel",
  "project_id": "0038dd52-560d-5796-87a7-9ca934e086ca",
  "project_slug": "alpha-lab",
  "timeline_id": "e5b84ea4-b110-5d95-9c26-1a0f8700dfa4",
  "timeline_ulid": "nre0n2zyktcbyw06v6a4m42fh4",
  "timeline_slug": "alpha-layer",
  "config_version": 1,
  "head_event_id": "fe4a66963e844283be1608db73bcdf00",
  "head_hash": "e8aba446a706d1307e8dd7aa37b1cb3537741e53f37e650a54b241e442bb2554",
  "config_hash": "00e25f668910db050ab35ab782ca17c9325edffee90e9b790eab5453f2a95197",
  "registry_hash": "917c9dd6b3827ebd1df91cc3f8dad532f64102cafd796a2ff59b41f2c0630d30",
  "materialized_registry_hash": "917c9dd6b3827ebd1df91cc3f8dad532f64102cafd796a2ff59b41f2c0630d30"
}
```

`timelines show` and `timelines history` independently returned the same
timeline identity, exact stamp/content, and version 1. `runs show` retained
the same complete authority object as immutable run input.

### Generic project SDK and MP4 control

Calling public `sdk.invoke_result("rendering.render")` with the project-owned
materialized stamped timeline and `output_name:"sdk-alpha.mov"` succeeded as
run `e000840a0a1eb7a14356ae97f9`. It reused the identical alpha media digest
while publishing a separately hashed provenance sidecar. This proves the raw
project SDK path and canonical product CLI share the corrected contract.

The version-pinned opaque control:

```bash
python3 -m astrid timelines render opaque --project alpha-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name opaque-control.mp4 --json
```

succeeded as run `2d2b7808e6a56a2b82fc636d06`. It probed H.264 High/
`yuvj420p` + AAC LC 48 kHz stereo; decoded alpha was `255..255` and the corner
was `(0,0,0,255)`. The existing `.mp4` behavior is unchanged.

### Incompatible explicit alpha profile

An explicit alpha MOV request using H.264/`yuv420p`/AAC returned:

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "alpha MOV output has an incompatible explicit render profile: video_codec='h264' (requires 'prores'); pixel_format='yuv420p' (requires 'yuva444p12le'); audio_codec='aac' (requires 'pcm_s16le')",
    "details": {
      "kernel_run_id": null,
      "kernel_task_id": null,
      "kernel_attempt_id": null,
      "run_id": null
    }
  }
}
```

The run count remained three before and after. This closes the prior late-
failure loophole for incompatible explicit profiles.

### Focused verification

```text
pytest -q tests/core/rendering/test_output_name.py \
  tests/core/rendering/test_service.py \
  tests/packs/rendering/test_managed_timeline_render.py \
  tests/packs/rendering/test_remotion_backend.py -x

144 passed in 91.33s
```

### Updated acceptance matrix

| Requirement | Direct documented SDK | Project/canonical route |
| --- | --- | --- |
| z>0 + exact alpha stamp to `.mov` | Pass | Pass |
| ProRes 4444 + `yuva444p12le` | Pass | Pass |
| Real transparent RGBA pixels | Pass | Pass |
| Durable managed MOV + correct MIME/suffix metadata | N/A | Pass |
| Exact pinned kernel authority in provenance | N/A | Pass |
| Unstamped `.mov` before admission | Pass (pre-render) | Pass (null IDs/no run) |
| Incompatible explicit MOV profile before admission | Pass | Pass (null IDs/no run) |
| Opaque `.mp4` H.264/AAC | Pass | Pass |

Severity after correction: **resolved**. Remaining P3 observations about lock
files and opaque `yuv420p`/`yuvj420p` spelling are unchanged and outside this
managed-integration defect.
