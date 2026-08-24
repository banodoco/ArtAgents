# Replay: canonical render profile UX 5

Date: 2026-08-24

Mode: independent black-box live agent usage. I used public `timelines render`
help, product CLI commands, public `media show`, and `ffprobe` against the
disposable output. I did not inspect or edit source/tests/product code.

Fresh disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-render-profile-replay-dRMzkP`

## Verdict

**PASS with one compatibility-friction note.** Nested/partial profiles fail
before admission with typed, actionable flat-schema diagnostics, null run IDs,
unchanged ledger state, and no render snapshot. The complete profile example
copied verbatim from `timelines render --help` renders successfully when the
canonical timeline declares the same 320x180 theme canvas. Provenance records
the exact profile and ffprobe confirms the requested dimensions, frame rate,
video/audio codecs, and audio parameters.

## Help contract

The public help advertises `--profile JSON` as a flat RenderProfile v1 object,
explicitly rejects `video`/`audio` nesting, documents the audio trio rule, and
prints this complete Remotion MP4 example. I copied it without changing any
field or value:

```json
{"width":320,"height":180,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

## Nested/partial preflight

Created project `profile-preflight` and a valid canonical empty timeline
`empty` (version 1, timeline id
`e585623d-3f67-5a25-84f4-a476e78f4e83`). First submitted the intuitive nested
profile:

```json
{"video":{"width":320,"height":180},"audio":{"codec":"aac"}}
```

The public command returned one stable five-key envelope with:

```text
code: validation_error
sdk_category: validation
sdk_error: CapabilityValidationError
message: invalid render profile: missing required field(s): width, height,
fps_rational, time_base, container, video_codec, video_profile, video_level,
pixel_format, duration_tolerance; unknown field(s): audio, video. --profile
uses the flat RenderProfile v1 object (no video/audio nesting); audio_codec,
audio_sample_rate, and audio_channel_layout must be supplied together or all
omitted. Complete Remotion MP4 example: {the exact flat JSON above}
```

All run/task/attempt IDs were null and `receipt` was null. Public `runs list`
remained `[]`; project `event_head_seq` remained 3; and no
`.astrid/render-snapshots` files existed.

Then submitted a flat profile with only `audio_codec` from the audio trio:

```json
{"width":320,"height":180,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","duration_tolerance":1}
```

It again failed pre-admission with `validation_error` and the direct recovery:
`audio_codec, audio_sample_rate, and audio_channel_layout must be provided
together or all omitted.` The flat-schema recovery/example was repeated in the
same message. Runs stayed empty, event head stayed 3, and no snapshot was
created.

## Complete profile render

I first copied the complete help example unchanged against the default empty
timeline canvas (1920x1080). That request was admitted but failed with a typed
runtime error:

```text
rendering.remotion does not support this render request: requested profile is
not produced by Remotion: width=320 (requires 1920); height=180 (requires 1080)
```

This exposed a documentation/context friction: the help example is only
compatible when the canonical theme canvas is also 320x180. I did not alter the
profile. Instead, I CAS-saved the timeline at version 2 with the explicit
canonical theme canvas `width=320`, `height=180`, `fps=30`, then reran the same
unchanged profile JSON.

The render succeeded:

- kernel run: `4d5c86e14c3f25c28a63dcc9e7`
- task: `db7f8e1e30f70dcaafeb14bb85`
- attempt: `01m0smnd9wvw5ykw3c2exdd349`
- primary media id: `01m0smnhpy5zkwm5bmn0v7v5b6`
- primary hash: `9d9ddc06f70de7f26fe3b952ddb60b97d3a5145e6fe20feaadd041ebab44ae92`
- provenance media id: `01m0smnhq1fjyb5yx3at2fspsx`
- requested output: `profile-example.mp4`

Public `media show` reported the primary as managed-local `video`, with a
decodable MP4 probe, video and audio streams, and durable CAS locator.

The provenance sidecar's `artifact_profiles[0].profile` exactly recorded:

```json
{
  "width": 320,
  "height": 180,
  "fps_rational": [30, 1],
  "time_base": [1, 90000],
  "container": "mp4",
  "video_codec": "h264",
  "video_profile": null,
  "video_level": null,
  "pixel_format": "yuv420p",
  "audio_codec": "aac",
  "audio_sample_rate": 48000,
  "audio_channel_layout": "stereo",
  "duration_tolerance": 1
}
```

`ffprobe` of the durable CAS artifact confirmed:

- container: MP4 (`mov,mp4,m4a,3gp,3g2,mj2`)
- video: H.264 High, 320x180, 30/1 fps
- audio: AAC-LC, 48000 Hz, stereo
- duration: 0.085333 seconds

The encoder reports `yuvj420p` through ffprobe while the provenance records
the requested `yuv420p`; this is a minor representation mismatch worth
watching, but dimensions, rate, codecs, and audio trio are correct and the
file is playable/decodable.

## UX assessment

- **Pre-admission diagnostics: 10/10.** Unknown nested fields and all missing
  flat fields are named; recovery and the exact working example are supplied.
- **No-side-effect truth: 10/10.** Invalid profiles produced no run, receipt,
  task/attempt IDs, or snapshot.
- **Successful profile path: 9/10.** Exact help example works after matching
  the canonical theme canvas; first-time agents may not know that implicit
  compatibility condition.
- **Artifact/provenance: 9/10.** Durable media, exact profile sidecar, and
  ffprobe evidence agree on the meaningful output contract; pixel-format
  aliasing remains a small ambiguity.

Overall: **9.5/10 — PASS.**
