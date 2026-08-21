---
name: understanding
description: >
  Understanding pack: modality-specific LLM inspection executors for
  audio, images, video, and scene captioning.  Includes a legacy
  dispatcher (understand) — prefer the specific executors for new work.
---

# Understanding

The understanding pack covers five executors for inspecting and describing
media with LLMs. Each executor targets a specific modality.

## Modality decision table

| Modality | Executor | Model family | What it does |
|---|---|---|---|
| Audio (clips, sampled windows) | `understanding.audio_understand` | OpenAI GPT Audio | Inspect audio with an audio-native LLM. Fast and best model presets available. JSON output. |
| Image (still frames, screenshots) | `understanding.visual_understand` | OpenAI Vision (GPT-4o) | Inspect images with a vision model. Supports free-text queries and JSON-schema-constrained structured output. |
| Video (synchronized audio+video) | `understanding.video_understand` | OpenAI Vision + Audio | Inspect synchronized audio/video windows. Pipeline step 5.5 — sits between scene_describe and quote_scout. |
| Scene captioning (pipeline step 5) | `understanding.scene_describe` | OpenAI Vision | Caption detected scenes for the editorial pipeline. Produces `scene_descriptions.json`. Depends on editorial.scenes + editorial.triage. |

## Legacy dispatcher

| Executor | Status | Notes |
|---|---|---|
| `understanding.understand` | **Legacy** | Dispatches to audio, visual, or video understanding based on `--mode`. Prefer using the specific executors above for new work — they offer clearer modality contracts and better model preset defaults. |

The `understand` executor accepts a `mode` input of `audio|image|visual|video` and
routes to the corresponding underlying executor. It exists for backward
compatibility; direct executor invocation gives you access to
modality-specific flags and model presets.

## Model presets

| Executor | Preset | Model | Use case |
|---|---|---|---|
| audio_understand | `fast` | gpt-4o-audio-preview | Quick audio inspection, lower cost |
| audio_understand | `best` | gpt-4o-audio-preview | Highest quality audio analysis |
| visual_understand | `fast` | gpt-4o-mini | Quick image inspection |
| visual_understand | `best` | gpt-4o | Detailed image analysis, structured output |
| video_understand | `fast` | gpt-4o | Fast video window inspection |
| video_understand | `best` | gpt-4o | Thorough audio+video window analysis |
| scene_describe | `best` | gpt-4o | Scene captioning with vocabulary-locked enums |

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | All understanding executors (OpenAI API) |

## Quick-start

```python
# Audio understanding (fast preset)
import astrid.sdk as sdk
result = sdk.invoke(
    "understanding.audio_understand",
    inputs={"audio": "./clip.mp3", "preset": "fast"},
    out="./out",
)

# Visual understanding with structured output
result = sdk.invoke(
    "understanding.visual_understand",
    inputs={"image": "./frame.png", "query": "Describe the scene"},
    out="./out",
)

# Video understanding (synchronized audio+video window)
result = sdk.invoke(
    "understanding.video_understand",
    inputs={"video": "./clip.mp4"},
    out="./out",
)

# Scene captioning (pipeline step 5)
result = sdk.invoke(
    "understanding.scene_describe",
    inputs={"video": "./source.mp4", "scenes": "./out/scenes.json"},
    out="./out",
)

# Legacy dispatcher (prefer specific executors)
result = sdk.invoke(
    "understanding.understand",
    inputs={"mode": "audio", "audio": "./clip.mp3"},
    out="./out",
)
```
