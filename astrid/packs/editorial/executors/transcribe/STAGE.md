# Transcribe

**Executor**: `editorial.transcribe`  
**Status**: implemented  
**Pipeline step**: 0 (entry point)

Transcribes source audio into a structured `transcript.json` file using
OpenAI's Whisper model. The executor handles audio extraction from video
sources, silence-aware chunking, and optional speaker diarization via
pyannote.audio. Output includes word-level timestamps and segment
metadata consumed by every downstream editorial step.

Requires an OpenAI API key (resolved via the candidate-env-file walk in
`astrid/core/util/secrets.py`). Whisper is called through the OpenAI API;
no local model installation is required.

## CLI quick-start

```bash
python -m astrid executors run editorial.transcribe -- \
  --audio ./source.mp3 --out ./out
```

With an explicit env file for API credentials:

```bash
python -m astrid executors run editorial.transcribe -- \
  --audio ./source.mp3 --env-file .env.local --out ./out
```

## Inputs

| Name     | Type | Required | Description                              |
|----------|------|----------|------------------------------------------|
| audio    | file | yes      | Audio or video-derived audio to transcribe |
| env_file | file | no       | Optional environment file for API credentials |

## Outputs

| Name       | Type | Path                      | Description              |
|------------|------|---------------------------|--------------------------|
| transcript | file | `{out}/transcript.json`   | Structured transcript JSON |

## Pipeline position

Step 0 of the editorial pipeline. No upstream dependencies — transcribe is the
entry point. It provides `transcript` to all downstream stages.

## Depends on

None (entry-point executor).
