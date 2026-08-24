# Replay render result 3 — live usage

**Verdict: PASS**  
**Run date:** 2026-08-23  
**Fresh root:** `/tmp/astrid-live-render3.MVusrx`  
**Project:** `title-render`

## Scope

Fresh-agent replay through the project-scoped SDK capability
`rendering.render` (no pytest, source-level test, or prior QA report). The
timeline was authored inside the managed project and contained a visible
2-second `HELLO ASTRID` text clip. Both renders used the explicit 640×360
profile and the strict `rendering.remotion` selector:

```json
{
  "width": 640,
  "height": 360,
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

## Evidence

### Render 1: `title-640.mp4`

- Invocation run `4e93c9ffd4ea5e4dae1fc0bfec` and child task
  `0ff0a0ad437af672452b9d16b5` both reached `succeeded`.
- InvocationResult primary artifact label and requested name were both
  `title-640.mp4`.
- Primary artifact media ID:
  `01m0qtavh08kb80vzgsk7ysh93`.
- Primary artifact path was durable managed media (no `.staging`):
  `/tmp/astrid-live-render3.MVusrx/projects/.astrid/media/sha256/cb/84/cb84a58806330eb6a924915a779f5a79ff690ed5fc9dcf550a30c8c44efc7b9b`.
- MP4 SHA-256:
  `cb84a58806330eb6a924915a779f5a79ff690ed5fc9dcf550a30c8c44efc7b9b`.
- Provenance artifact was also durable managed media at
  `/tmp/astrid-live-render3.MVusrx/projects/.astrid/media/sha256/12/df/12df7d86033a5569cdf0347033eff92cf9f1f93a18409960c749affc27de8a19`,
  with media ID `01m0qtavh5t2f9rkgadb0dvr96` and SHA-256
  `12df7d86033a5569cdf0347033eff92cf9f1f93a18409960c749affc27de8a19`.
- Provenance `output` points to the durable MP4 locator above; its
  `artifact_profiles[0].sha256` equals the MP4 SHA-256 and its profile records
  640×360, 30 fps, 1/90000 time base, H.264, and AAC stereo 48 kHz.

### Render 2: `title-640-copy.mp4` (same bytes, dedupe)

- Invocation run `f9fc09f2375dc6dbc7037ad7d7` and child task
  `a88152b27bac4afaef28aa6c0c` both reached `succeeded`.
- InvocationResult primary artifact label and requested name were both
  `title-640-copy.mp4`.
- The MP4 reused media ID `01m0qtavh08kb80vzgsk7ysh93` and the same
  content hash/path as render 1, proving content dedupe while retaining the
  current requested name in the result artifact.
- Its provenance remained a distinct durable managed artifact with current
  label/name `title-640-copy.mp4.provenance.json`, media ID
  `01m0qtbkfpf3215fhqeyc0kay3`, and SHA-256
  `a38ebc104d0f9608177f0e6b936a9c535915b9d5e3925e2443ebc3719d4dad18`.
- Its provenance `output` still points to the same durable MP4 locator and its
  `artifact_profiles[0].path` and SHA-256 reflect `title-640-copy.mp4` and the
  deduped MP4 bytes.

### ffprobe and visual inspection

`ffprobe` on the durable MP4 reported:

- video: H.264, 640×360, 30/1 fps, 1/90000 time base, 60 frames, 2.000 s;
- audio: AAC LC, 48,000 Hz, stereo;
- MP4 container, two streams, 2.048 s mux duration.

The reported `yuvj420p` is the full-range encoder spelling of the requested
`yuv420p`; Astrid's profile validation canonicalizes those names as equivalent.
A sampled frame at 1.0 s (`/tmp/astrid-live-render3.MVusrx/hello-frame.png`) is
640×360 and visibly reads `HELLO ASTRID` centered on the frame.

## Verdict

PASS. Project-scoped rendering succeeded twice through the live capability;
the explicit canvas/profile was honored; terminal run/task state was clean;
InvocationResult artifact paths were durable managed locators; MP4/provenance
hashes and media identity were internally consistent; dedupe preserved the
second requested label/name; and provenance retained a durable MP4 locator.
