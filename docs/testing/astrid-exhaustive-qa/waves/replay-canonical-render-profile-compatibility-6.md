# Replay: canonical render profile compatibility 6

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `--help` and `python3 -m astrid` CLI only  
Root: `/tmp/astrid-profile6-src-VUBU0y`  
Verdict: **PASS — no remaining profile-compatibility friction.**

Fresh project `profile6` used the default `banodoco-default` theme (no theme
override), default timeline `main`, one valid managed MP4, and a canonical
`clipType: "video"` timeline saved at version 2.

The profile was copied verbatim from the current `timelines render --help`
Remotion example:

```json
{"width":1920,"height":1080,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

The pinned public command succeeded with strict JSON stdout:

- run: `f5ce3d64d9e8140e538337e25d`
- task: `7b6d549efd6326e481cc399ac3`
- MP4 hash: `2241e61c3d6e18301f112176750f0e07ad1ca684a31f59beb597b6610ca4832a`
- provenance hash: `efe48c692c2f805a00f04c47d4ec84ca2cf61f7e8ae8bb40988f124fc75ee552`

`ffprobe` confirmed playable H.264/AAC output at 1920×1080, 60 video frames,
96 audio frames, and 2.048 seconds. Public `runs show --evidence` recorded
`authority: kernel`, `config_version: 2`, and the canonical/materialized
registry hashes.

The same profile was then changed only to `width: 320` and `height: 180`,
leaving the default theme and all other fields unchanged. The command failed
before admission with a typed `validation_error`:

```text
invalid render profile for canonical timeline 'main': width=320
(authoritative theme canvas produces 1920); height=180 (authoritative theme
canvas produces 1080). Explicit profiles must match the authoritative theme
canvas; use the default profile from timelines render --help or set
theme_overrides.visual.canvas to the requested width, height, and fps, then retry
```

The error carried null `kernel_run_id`, `kernel_task_id`, `kernel_attempt_id`,
and `run_id`. Run count stayed at 1, render-snapshot directory count stayed at
1, managed media count stayed at 3, and no `profile6-bad.mp4` or provenance
artifact was created.

## Remaining friction

None for this profile contract. The previous mismatch was an invocation-time
failure; the current public surface rejects it pre-admission with an
actionable theme-canvas explanation and a safe override path.
