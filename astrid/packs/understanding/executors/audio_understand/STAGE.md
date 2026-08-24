# Audio Understand

**Executor**: `understanding.audio_understand`  
**Status**: implemented  
**Kind**: LLM-backed audio inspection

Inspects audio clips or sampled windows using an audio-native LLM via the
OpenAI GPT Audio API. The executor sends raw audio data to the model and
receives structured JSON output describing the audio content — transcription,
speaker identification, emotional tone, background sounds, and music detection.

## Model presets

Two model presets are available:

| Preset | Model                    | Use case                              |
|--------|--------------------------|---------------------------------------|
| fast   | `gpt-4o-audio-preview`   | Quick inspection, low-latency         |
| best   | `gpt-4o-audio-preview`   | Detailed analysis (higher token cap)  |

Both presets use the same underlying model but differ in prompt strategy and
token budget. The executor produces JSON output consumable by downstream
analysis and clip-selection stages.

## API requirements

Requires an **OpenAI API key** resolvable via the candidate-env-file walk
(`astrid/core/util/secrets.py`). The executor makes HTTP calls to the
OpenAI GPT Audio endpoint — no local model installation is required.

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "understanding.audio_understand",
    kind="executor",
    project="demo",
    inputs={"audio": "./clip.mp3"},
)
```

With explicit model selection:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "understanding.audio_understand",
    kind="executor",
    project="demo",
    inputs={"audio": "./clip.mp3", "model": "gpt-4o-audio-preview"},
)
```

## Inputs

| Name  | Type | Required | Description                   |
|-------|------|----------|-------------------------------|
| audio | file | yes      | Audio clip to inspect         |

## Outputs

The project run contains `analysis.json` with the structured audio analysis
and `manifest.json` with the universal result manifest. No sentinel output —
this executor uses `cache.mode: none` and always runs when invoked.

## Pipeline position

Auxiliary executor — not in the numbered editorial pipeline. Called on-demand
for ad-hoc audio inspection.

## Depends on

None.

## Shared LLM API pattern

Like `understanding.scene_describe` and `understanding.video_understand`, this
executor follows the shared Astrid LLM pattern:
1. Resolve API key from environment
2. Select model (fast/best preset or explicit `--model`)
3. Send prompt + media to the API
4. Return structured JSON output
