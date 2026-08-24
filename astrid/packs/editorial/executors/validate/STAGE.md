# Validate

**Executor**: `editorial.validate`  
**Status**: implemented  
**Pipeline step**: 14 (schema validation against arrangement and cut outputs)

Validates the rendered hype.mp4 against the declared timeline and metadata.
The executor runs a fresh Whisper transcription on the output video, then for
each audio clip in hype.timeline.json, compares the transcribed audio in that
clip's timeline range against the `source_transcript_text` recorded in
hype.metadata.json. Token-set similarity (default threshold 0.5) gates each
clip pass/fail. Visual-only captions and clips without metadata entries are
skipped. Produces `validation.json` with per-clip results and a summary.
Exits non-zero when any non-skipped clip falls below the threshold — making
this the final quality gate before publish.

The validator also detects caption misalignment: if expected text appears
elsewhere in the full transcript but not within the clip's time window, it
flags the clip with a `note` indicating likely misalignment.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.validate",
        kind="executor", project="demo",
    inputs={"video": "./out/hype.mp4"},
)
```

With explicit timeline and metadata paths:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.validate",
        kind="executor", project="demo",
    inputs={
        "video": "./out/hype.mp4",
        "timeline": "./out/hype.timeline.json",
        "metadata": "./out/hype.metadata.json",
        "threshold": "0.6",
    },
)
```

With an env file for the Whisper API key and skipping re-transcription:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.validate",
        kind="executor", project="demo",
    inputs={
        "video": "./out/hype.mp4",
        "env_file": ".env.local",
        "skip_transcribe": True,
    },
)
```

## Inputs

| Name      | Type | Required | Description                                           |
|-----------|------|----------|-------------------------------------------------------|
| video     | file | no       | Rendered hype.mp4 to validate                         |
| timeline  | file | no       | hype.timeline.json (defaults to <video-dir>/hype.timeline.json) |
| metadata  | file | no       | hype.metadata.json (defaults to <video-dir>/hype.metadata.json) |
| env_file  | file | no       | Env file forwarded to transcribe for Whisper API key  |

## Outputs

| Name       | Type | Path                          | Description                      |
|------------|------|-------------------------------|----------------------------------|
| validation | file | `{brief_out}/validation.json`  | Per-clip pass/fail/skip report with similarity scores |

## Pipeline position

Step 14 of the editorial pipeline. This is the final quality gate — it runs
after rendering.render (step 12) and editorial.editor_review (step 13).
The validation report is the last artifact before publish. Because it depends
on the entire upstream pipeline (through render and editor_review), it
provides end-to-end assurance that the rendered video matches the creative
intent.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build`
- `training.pool_merge`
- `editorial.arrange`
- `video_editing.cut`
- `editorial.refine`
- `rendering.render`
- `editorial.editor_review`
