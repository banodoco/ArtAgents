# MiniMax H3 video via fal.ai

Use `fal.h3_video` for MiniMax H3 text-to-video and multimodal
reference-to-video generation.

Official endpoint constraints:

- exact prompt length: 1–2,000 characters;
- generated duration: 5–15 seconds;
- resolution: fixed 2K;
- text mode aspect ratios: 21:9, 16:9, 4:3, 1:1, 3:4, or 9:16;
- reference mode: up to nine images, three videos, three audio clips, and
  twelve files total; audio cannot be the only reference modality.

Run through the SDK:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "fal.h3_video",
        kind="executor", project="demo",
    inputs={
        "project": "<slug>",
        "mode": "text-to-video",
        "prompt_file": "./prompt.txt",
        "duration": "15",
        "aspect_ratio": "16:9",
    },
)
```

For reference mode, repeat ordered inputs:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "fal.h3_video",
        kind="executor", project="demo",
    inputs={
        "project": "<slug>",
        "mode": "reference-to-video",
        "prompt_file": "./prompt.txt",
        "image_ref": ["./image1.png", "./image2.png"],
        "duration": "15",
        "aspect_ratio": "16:9",
    },
)
```

Every non-dry run is paid. Make one explicit attempt per prompt. Preserve the
generated run bundle and inspect `manifest.json` before retrying.
