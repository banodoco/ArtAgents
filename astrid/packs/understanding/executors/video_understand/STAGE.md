# Video Understand

**Executor**: `understanding.video_understand`  
**Status**: implemented  
**Pipeline step**: 5.5 (between scene_describe and quote_scout)

Inspects synchronized audio+video windows using a video-understanding model
via the OpenAI GPT Video API (or compatible multimodal endpoint). The executor
extracts short video segments around key moments identified by earlier pipeline
stages and sends them to the model for holistic audio-visual analysis.

Unlike `audio_understand` (audio-only) and `scene_describe` (vision-only),
this executor processes **synchronized audio and video together**, enabling
the model to reason about speech-to-action alignment, on-screen speaker
identification, and the interplay between visual and auditory content.

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "understanding.video_understand",
        kind="executor", project="demo",
    inputs={"video": "./source.mp4"},
)
```

## Inputs

| Name  | Type | Required | Description              |
|-------|------|----------|--------------------------|
| video | file | no       | Video to inspect         |

## Outputs

JSON output written to stdout/stderr with synchronized audio+video analysis
results. No sentinel output — this executor uses `cache.mode: none` and
always runs when invoked.

## Pipeline position

Step 5.5 — a fractional step between `understanding.scene_describe` (step 5)
and `editorial.quote_scout` (step 6). Provides richer multimodal context for
quote selection and clip triage.

## Depends on

None declared in the dependency graph (ad-hoc inspection executor).

## Shared LLM API pattern

Like `understanding.audio_understand` and `understanding.scene_describe`,
this executor follows the shared Astrid LLM pattern:
1. Resolve API key from environment
2. Select model (prompt-configurable)
3. Send synchronized audio+video to the multimodal API
4. Return structured JSON output

Requires a multimodal-model-compatible API key (OpenAI or compatible provider
with video+audio understanding support).
