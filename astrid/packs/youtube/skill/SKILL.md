---
name: youtube
description: >
  YouTube pack — acquire YouTube media (audio MP3 / video MP4 via yt-dlp)
  and publish finished videos to YouTube via Zapier social integration.
---

# YouTube

The youtube pack ingests YouTube media for downstream use and publishes
finished videos to YouTube. It does not edit or render — only acquire and
publish.

## Executors

| Executor | What it does |
|---|---|
| `youtube.youtube_audio` | Download a YouTube video's audio (MP3) or video (MP4) — by search query or direct URL. Uses yt-dlp. |
| `youtube.upload` | Upload a finished video to YouTube via the shared banodoco-social Zapier integration. |

## When to use

- Use `youtube.youtube_audio` to fetch source audio/video from YouTube for
  downstream editing or understanding.
- Use `youtube.upload` to publish a finished rendered video to YouTube.

## When NOT to use

- Do not use to edit or render the video itself — use `video_editing`.
- Do not use to analyze content — use `understanding`.
- This pack only ingests and publishes.

## Quick-start

```python
# Download audio by search query
import astrid.sdk as sdk
result = sdk.invoke(
    "youtube.youtube_audio",
    inputs={"query": "cool synthwave mix"},
    out="./audio.mp3",
)

# Download audio by URL
result = sdk.invoke(
    "youtube.youtube_audio",
    inputs={"url": "https://youtube.com/watch?v=..."},
    out="./audio.mp3",
)

# Upload a finished video
result = sdk.invoke(
    "youtube.upload",
    inputs={"video": "./hype.mp4", "title": "My Hype Video"},
)
```
