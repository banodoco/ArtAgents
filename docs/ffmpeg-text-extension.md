# FFmpeg Text Rendering Extension

## Problem

The `rendering.ffmpeg` backend currently declares `clip_types: [media]` and `features: media_only: true`.
This means any timeline with text clips (captions, wordmarks, titles) routes to Remotion —
which requires Chrome headless, webpack bundling, and 189+ Google Fonts CDN requests per render.

For slide-based videos (static images + text overlay + audio), this is massive overhead for zero benefit.
FFmpeg handles all of this natively via `drawtext`, `overlay`, and `concat` filters.

## Current state

- `rendering.ffmpeg` backend: `astrid/packs/rendering/backends/ffmpeg/` (736 lines in run.py)
- Supports: media clips only (images, audio)
- Does NOT support: text clips, fade envelopes, transitions
- Auto-routing: `legacy_hybrid` planner prefers ffmpeg for media-only, falls back to Remotion for text

## What needs to change

### 1. `renderer.yaml` — declare text support

```yaml
capabilities:
  clip_types:
    - media
    - text        # ADD: text clips now supported
  features:
    media_only: false   # CHANGE: we now handle text
    text_overlay: true
    fade_envelope: true
```

### 2. `run.py` — text clip handling

For each text clip in the timeline:

1. **Rasterize** the text to a transparent PNG using PIL:
   - Font: system monospace or bundled woff2
   - Size, color, weight, alignment from `clip.text`
   - Position from `clip.params` (anchor, offsetX, offsetY)
   - maxWidth for wrapping
   - textShadow
2. **Overlay** the PNG onto the b-roll image using ffmpeg's `overlay` filter:
   - Position: `x` / `y` from anchor computation
   - Timing: `enable='between(t,start,end)'`
   - Fade: `alpha='if(lt(t,start+fade),t-start/fade,...)'`

3. **Composite all text overlays** into a single filtergraph per section (not one ffmpeg call per text clip)

### 3. Fade envelope

The timeline's `effects.fade_in` / `effects.fade_out` map to overlay alpha:

```
alpha = 'if(lt(t,at+fade_in),(t-at)/fade_in, if(gt(t,at+hold-fade_out),(at+hold-t)/fade_out, 1))'
```

Applied to the text overlay via `colorchannelmixer=aa=` or `format=rgba,colorchannelmixer=aa=`.

### 4. Support check

`support.py` must return `supported=True` when the timeline contains media + text clips.
Currently it returns unsupported for anything with non-media clip types.

## Implementation order

1. Add `_rasterize_text_clip()` helper using PIL (font, size, color, wrap, shadow)
2. Extend the ffmpeg filtergraph builder to chain overlays for text PNGs
3. Add fade envelope to the overlay filter expression
4. Update `support.py` to accept text clips
5. Update `renderer.yaml` capabilities
6. Test with the intro storyboard (76 clips / 50 assets / 177.53s)

## Why this matters

- **Speed**: ffmpeg render takes seconds vs minutes with Remotion (no Chrome, no webpack, no CDN)
- **Reliability**: no Google Fonts CDN dependency, no npm dependency tree fragility
- **Simplicity**: one binary (ffmpeg) instead of Chrome headless + webpack + Node.js
- **Offline**: renders work without internet access
