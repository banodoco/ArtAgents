# Replay: render provenance 2

## Verdict

**FAIL for the requested 640×360 guard; PASS for the 1920×1080 render and
provenance path.** The live project-scoped flow can create and render the title,
but it does not reject 640×360 before producing an artifact. A fully specified
640×360 `astrid.support("rendering.remotion", ...)` request returned
`supported: true`, and the first project-scoped render produced a real
640×360 MP4. Supplying a `profile` mapping to the project-scoped
`rendering.render` executor was silently ignored rather than validated.

## Live setup and UX path

- Fresh root: `/tmp/astrid-title-render-np12CC` via `ASTRID_PROJECTS_ROOT`.
- Public census/help, Astrid skill, render `STAGE.md`, SDK reference, and
  render-backend contract were read first.
- Created project `title-render` with the public CLI, then created timeline
  `title` with one 2-second text clip (`HELLO ASTRID`) on a dark background.
- No pack `run.py` was invoked directly. Rendering used
  `astrid.sdk.invoke("rendering.render", kind="executor", project="title-render", ...)`.

## 640×360 rejection attempt

The exact 640×360 profile used for the probe was:

```json
{"width":640,"height":360,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

`astrid.support("rendering.remotion", ...)` returned `supported: true` with
no reasons. The first project-scoped render (`run_id`
`b66167c2462cf5c5d20c7349b4`, task `7fa75b1405156723825b8609c0`) also
succeeded and produced `title-640.mp4`; ffprobe showed 640×360, 30/1, and
60 frames. This is the central acceptance failure: there was an artifact
instead of an actionable unsupported-profile error.

I also passed the same 640×360 `profile` mapping to the canonical project
executor while the timeline canvas was 1920×1080. That invocation succeeded
(`run_id` `ac8af44e596fe25a5a1e7c5e03`) and produced a 1920×1080 artifact,
confirming that the project-scoped executor currently does not expose or
validate the profile request.

For comparison, a deliberately invalid renderer rejection produced a useful
primary `InvocationResult.error`:

```json
{"type":"RendererUnsupportedError","sdk_error":"CapabilityRuntimeError","sdk_category":"runtime","reason":"handler_failed","message":"unknown renderer id 'rendering.ffmpeg-finalizer'"}
```

That error is clear, but it is not the required 640×360 supported-profile
guidance.

## Recovery to 1920×1080

Following the intended guidance, I saved timeline version 2 through the public
CAS CLI with canvas `1920×1080 @ 30 fps`, then invoked the project-scoped
renderer with `backend: rendering.remotion` and `output_name: title.mp4`.

- Final run: `1ca10dc3945bd3ac1e432d4be1`
- Final task: `4fd676fef4a424c27f84d5ed68`
- Run status: `succeeded`, one child, one succeeded
- Task status: `succeeded`, attempt 1, terminal completion
- Ordered task outputs:
  1. MP4 media ID `01m0qrz3czyeb5f8h5pgv6rka4`, SHA-256
     `6fc0afd3614ffb07a088522c583cef7928ee7b0b1e2494d1f145922e90756e39`
  2. Provenance media ID `01m0qrzxqgfnpykwmhh167ezgx`, SHA-256
     `82646c8ffd3b5d3664f939529226eccbaa43cbdbdb680faa3851c8359dac45ac`
- InvocationResult output paths:
  - MP4: `/private/tmp/astrid-title-render-np12CC/.astrid/media/.staging/ff5e6e52b98c4f6d8c030a783976a3ee/title.mp4`
  - Provenance: `/private/tmp/astrid-title-render-np12CC/.astrid/media/.staging/ff5e6e52b98c4f6d8c030a783976a3ee/title.mp4.provenance.json`
- Managed MP4 location verified through `media verify`:
  `/private/tmp/astrid-title-render-np12CC/.astrid/media/sha256/6f/c0/6fc0afd3614ffb07a088522c583cef7928ee7b0b1e2494d1f145922e90756e39`
- Managed provenance location:
  `/private/tmp/astrid-title-render-np12CC/.astrid/media/sha256/82/64/82646c8ffd3b5d3664f939529226eccbaa43cbdbdb680faa3851c8359dac45ac`

The content-addressed MP4 media row retains `rel_path: reject-640.mp4` because
the earlier 1920×1080 artifact from the profile-ignored probe had identical
bytes and was deduplicated. The bytes, hashes, and final output are still
consistent, but the stale display name is an additional provenance/UX wrinkle.

## Independent media evidence

Final MP4 ffprobe:

```text
codec=h264  size=1920x1080  r_frame_rate=30/1  avg_frame_rate=30/1
time_base=1/90000  nb_frames=60  duration=2.048000
audio=aac  time_base=1/48000  nb_frames=96
```

The provenance sidecar declares the same 1920×1080 profile, 30/1 FPS,
`h264`, `yuv420p`, `aac`, stereo, and MP4 SHA-256. A frame extracted at
`-ss 1` is at:

`/tmp/astrid-title-render-np12CC/title-render/title-frame.png`

It is a 1920×1080 PNG (SHA-256
`dd4671803c434fed004e60c2039aaee4d57582ba6bf051195c9afa51b38922a1`) and
visibly shows white `HELLO ASTRID` centered on a black/dark background.

## Follow-up UX fix target

Make `rendering.render` accept an explicit render profile/window through the
project-scoped public invocation, run the same support check at admission,
reject unsupported 640×360 before any media row/artifact is created, and
return a typed error whose message names the supported 1920×1080 profile. Also
avoid retaining a prior deduplicated filename as the visible output name when
the current invocation has a different `output_name`.
