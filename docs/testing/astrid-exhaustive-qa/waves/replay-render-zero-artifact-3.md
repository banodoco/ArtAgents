# Replay render zero-artifact — wave 3

Date: 2026-08-23  
Surface: public Python rendering SDK (`astrid.render`)  
Backend: `rendering.remotion`  
Verdict: **PASS**

## Scope and isolation

This was a fresh black-box live UX replay. I used only the documented
`astrid.render(timeline_path, backend=..., out_path=...)` surface and the
documented timeline JSON shape. No source, tests, git commands, or earlier QA
artifacts were used as inputs.

The isolated temporary root was
`/tmp/astrid-replay-render-zero-artifact-3.53JhoV` (removed at the end). The
output parent was an empty `parent/` directory. Its initial normalized file
snapshot was empty. Timeline inputs lived outside that parent.

## Invalid submissions

1. Structured text without `clipType`, output name `bad-text.mp4`:

   - Typed exception: `RendererUnsupportedError`.
   - Frozen error kind: `unsupported`.
   - Actionable reason: `clips[0] contains structured text; set clipType to 'text'`.
   - Recovery listed selectable alternatives (`rendering.ffmpeg`,
     `rendering.threejs`).

2. Valid text with output name `bad-suffix.mov`:

   - Typed exception: `RendererProtocolError`.
   - Frozen error kind: `protocol`.
   - Actionable message: `output_name must end in .mp4 for the selected render
     profile; got 'bad-suffix.mov'`.
   - Recovery: retry with an output name ending in `.mp4`.
   - Details identified `required_suffix: .mp4` and the submitted name.

After each failed call, the output parent remained empty. The before/after
file snapshot at both failed checkpoints had no entries: no output, replay
bundle, staging directory, run/task/media tree, or SQLite kernel was created.

## First valid render

The minimal valid timeline used one visual track (with its required `label`),
one one-second `text` clip, and `clipType: "text"`. The first call succeeded:

```text
/tmp/astrid-replay-render-zero-artifact-3.53JhoV/parent/valid.mp4
```

The published file was 49,074 bytes and 1.045333 seconds. `ffprobe` reported:

- video: H.264 / AVC, High profile, 1920×1080, 30 frames;
- audio: AAC-LC, 48 kHz, stereo, 49 frames;
- container: MP4 (`mov,mp4,m4a,3gp,3g2,mj2`).

The first decoded frame was not blank: `signalstats` reported `YMIN=0`,
`YMAX=255`, and `YAVG=0.145576`; decoding the frame to PNG visibly showed the
white word `VALID` on the black canvas. The only retained parent files after a
successful call were the expected MP4, its provenance sidecar, and the
zero-byte publication lock. No temporary render-service directory remained;
no replay/staging/run/task/media directory or kernel database existed.

The direct rendering SDK path does not use the kernel admission path, so a
kernel doctor check was not applicable. No `doctor` invocation was needed or
performed, and the isolated root contained no `.astrid`/SQLite state.

## Cleanup and code state

The temporary root and all generated media were removed after evidence capture.
No source or test files were changed; only this QA wave document was added.
