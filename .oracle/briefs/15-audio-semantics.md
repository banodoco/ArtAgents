# Explore: timeline audio control semantics

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

The FFmpeg backend's strict support reporting must know exactly what the
timeline schema allows for audio, so it can reject or implement track-level
mute, clip mute, volume, and fades.

1. Timeline schema: `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`
   and any Python mirror (`astrid/core/timeline/` schemas, `astrid/timeline.py`):
   - What audio-related fields exist on tracks and clips? (kind audio, muted,
     volume, params.fadeIn/fadeOut, from/to trimming?) Quote the TypeScript
     and Python schema definitions.
   - Is track-level `muted` a real field? Clip-level mute? How do they
     interact (precedence)?
2. How Remotion TypeScript implements audio today: `remotion/node_modules/@banodoco/timeline-composition/typescript/src/` —
   AudioTrack.tsx (or equivalent): how muted/volume/fades are applied per
   frame. Quote the volume function.
3. How the Python FFmpeg path (`astrid/packs/rendering/executors/render/run.py`)
   handles the same fields today: which are honored (volume? fades?), which
   are silently ignored, and where. Does the ffmpeg media validator reject
   timelines with muted tracks / fades / overlaps?
4. Existing tests covering audio semantics (tests/packs/rendering/*, tests/timeline/*):
   list what they assert about mute/volume/fade.

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts (field inventory + precedence)
- Unknowns
- Risks for strict FFmpeg support reporting
- Suggested approach (the exact audio-support rules the validator should express)
