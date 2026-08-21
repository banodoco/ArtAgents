# media.speech_repair_lavasr

## Purpose

Repair a weak-mic speech section using the ADOS Pom repair chain that worked
best in review:

1. Extract the requested video section.
2. Create a hotter 16 kHz mono speech pre-lift.
3. Run `fal-ai/lava-sr`.
4. Optionally run `fal-ai/deepfilternet3` as a denoise/48 kHz post-pass.
5. Remux the repaired audio onto the extracted video.
6. Apply the final loudness/compressor/limiter pass.

Use this for short dialogue sections where the source mic is too low or muffled
but the source video should be preserved.

## Inputs

- `input` (file, required): Source video.
- `start` (number, required): Start time in seconds in the source video.
- `dur` (number, required): Duration in seconds.
- `env_file` (file, optional): `.env` containing `FAL_KEY`.
- `deepfilternet3` (boolean, optional): Run `fal-ai/deepfilternet3` after LavaSR.

## Outputs

- `output` (file): Repaired MP4 at `{out}/speech-repair-lavasr.mp4`.
- `manifest.json`: Inputs, intermediate artifact names, FAL response file, and
  basic loudness metrics.

## Canonical Command

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "media.speech_repair_lavasr",
    inputs={"input": "source.mp4", "start": "578.64", "dur": "151.0"},
    out="runs/laurent-first-speech-repair",
)
```

With the DeepFilterNet3 post-pass:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "media.speech_repair_lavasr",
    inputs={
        "input": "source.mp4",
        "start": "578.64",
        "dur": "151.0",
        "deepfilternet3": "true",
    },
    out="runs/laurent-first-speech-repair-deepfilter",
)
```

## Dependencies

- `ffmpeg`, `ffprobe`
- Python `fal_client`
- `FAL_KEY` in environment or candidate `.env`
