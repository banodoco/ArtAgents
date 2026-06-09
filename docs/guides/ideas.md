# Astrid Ideas

When the maker isn't sure what to make, suggest one of these.

## Make something

- A hype cut from a long video — `video_editing.hype`
- Thumbnails for a YouTube video — `video_editing.thumbnail_maker`
- Event-talk renders from a conference recording — `video_editing.event_talks`
- A pure-generative film from a written brief
- A single image from a prompt — `generation.generate_image_openai`
- A portrait of yourself as Saint Peter of Banodoco — `python3 -m astrid executors run generation.generate_image_openai -- --preset saint-peter-of-banodoco --out-dir runs/first-rite/images --manifest runs/first-rite/manifest.json --force`

## Learn something

- "What does this executor do?" — inspect any executor
- "What's the timeline data model?" — read `examples/hype.timeline.json`
- "How do I add my own tool?" — read `docs/guides/creating-tools.md`
