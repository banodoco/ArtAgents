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

Run through the canonical gateway:

```bash
astrid executors run fal.h3_video --project <slug> \
  --input mode=text-to-video \
  --input prompt_file=./prompt.txt \
  --input duration=15 \
  --input aspect_ratio=16:9
```

For reference mode, repeat ordered inputs:

```bash
astrid executors run fal.h3_video --project <slug> \
  --input mode=reference-to-video \
  --input prompt_file=./prompt.txt \
  --input image_ref=./image1.png \
  --input image_ref=./image2.png \
  --input duration=15 \
  --input aspect_ratio=16:9
```

Every non-dry run is paid. Make one explicit attempt per prompt. Preserve the
generated run bundle and inspect `manifest.json` before retrying.
