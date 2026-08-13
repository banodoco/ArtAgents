# Explore: FFmpeg behavior, media normalization, and audio ownership

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. In `astrid/packs/rendering/executors/render/run.py`:
   - `_validate_ffmpeg_media_timeline` (or equivalent): what it accepts and
     what it rejects. Find fail-open gaps: visual gaps, overlapping audio,
     speed changes, missing sources, unsupported track/clip types — which of
     these are NOT validated?
   - `_render_ffmpeg_media` (or equivalent): how the ffmpeg command is built
     (filters? stream copy? silent audio synthesis?), how audio is handled,
     and the "audio-reactive-colour" specialization
     (`audio_reactive_colour.py`): what it produces, marker hash, fps, event
     count.
2. `astrid/core/media.py` MediaProbe: exactly which fields it captures today
   (codec? pixel format? time base? audio codec/sample rate/channel layout?
   duration? fps? dimensions?). Quote the dataclass/function.
3. `astrid/packs/video_editing/executors/cut/probe.py`: what it probes that
   `media.py` doesn't.
4. Audio ownership today: does ffmpeg always synthesize silence? Where?
   Which timeline audio features (muted tracks, volume, fades) flow into the
   ffmpeg path vs Remotion?
5. Where `ffmpeg` binary is located/validated (shutil.which? env?) and which
   existing tests cover ffmpeg command construction
   (tests/packs/rendering/*).

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks for extracting an FFmpeg backend + finalizer with audio ownership modes
- Suggested approach
