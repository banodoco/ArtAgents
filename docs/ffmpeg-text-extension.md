# FFmpeg Text Rendering Extension

## Problem

Slide-based videos (static images + text overlay + audio) used to route to
Remotion whenever a timeline contained a text clip, because
`rendering.ffmpeg` declared `clip_types: [media]` / `media_only: true`.
Remotion needs Chrome headless, a webpack bundle, and per-render font CDN
requests. FFmpeg can produce the same composite with one binary: PIL-rasterized
text PNGs composited over the video spine via `overlay` and `concat` — no
`drawtext`, no browser, no network.

## What shipped

`rendering.ffmpeg` now renders media + text timelines locally:

- `renderer.yaml` declares the capability: `clip_types: [media, text]`,
  `media_only: false`, `text_overlay: true`, `fade_envelope: true`.
- `text.py` rasterizes each text clip to a full-canvas transparent PNG.
- `run.py` builds the overlay specs and executes the command built by
  `command.py`; the filtergraph itself lives in `command.py`
  (`build_filter_graph`), not in a per-section loop in `run.py`.
- Select `rendering.ffmpeg` explicitly through `rendering.render` when the
  request's support report accepts the media/text matrix above. Unsupported
  requests fail closed with the support report; the host does not translate
  shorthand selectors or silently fall back to another backend. Select
  `rendering.remotion` explicitly for requests requiring that backend.

## How it works

### Text rasterization (`text.py`)

- **Font**: system TTFs only, fail-closed. Candidates in priority order:
  Supplemental Arial, `/Library/Fonts` Arial, DejaVu (Linux); bold requires a
  bold face or fails. No candidate → `FileNotFoundError` at rasterize time,
  and support rejects the request up front when no candidate exists. There is
  no `ImageFont.load_default()` fallback, no fonttools, no woff2, and no
  bundled PowerGrotesk. `text.fontFamily` and `italic` are ignored (fixed
  stack).
- **Color**: `_parse_color` resolves hex and named colors through PIL
  `ImageColor.getcolor`, and hand-parses `rgba(r, g, b, a)` because hype
  shadows carry float alpha. Support validates colors by calling the same
  helper — it never re-splits CSS strings.
- **Shadow**: `_parse_text_shadow` parses CSS
  `offsetX offsetY [blur] color` (3-part form omits blur). The shadow is
  painted on its own layer, blurred (`blur / 2` Gaussian sigma, matching
  canvas shadowBlur), alpha-composited under the text.
- **Fades**: `_parse_fades` reads `clip.effects` — the only fade reader for
  text clips, shared by `support.py` (validation) and `run.py` (spec
  building). Map form or list-of-objects; the list scan takes the first
  numeric `fade_in` and `fade_out` independently (Remotion getEffectValue
  semantics); missing/empty → `(0.0, 0.0)`.
- **Window**: `_text_window` wraps the canonical
  `_clip_duration_seconds` helper — `at` plus a positive duration via
  `hold`/`to`; a missing or non-positive duration fails. Text `from` is
  rejected by support (`use at with hold or to`).
- `rasterize_text_clip` paints the text (greedy wrap to `params.maxWidth`,
  anchor semantics matching ThreeTimelineComposition) onto a full-canvas RGBA
  PNG with position baked in. Fades are NOT baked into the PNG — the overlay
  filter applies them.

Overlay specs are ordered track-array order, then `at`, then clip index;
later entries composite on top.

### Filtergraph shape (`command.py`)

`build_filter_graph` emits one `filter_complex`. Visual media clips are
trimmed, scaled/padded to canvas, fps-normalized, and concat'd into a
`[vout]` spine; each text overlay PNG then composites on top:

```
[i:v]format=rgba,
fade=t=in:st=AT:d=FADE_IN:alpha=1,
fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1[ovK]
[spine][ovK]overlay=0:0:enable='between(t,AT,END)':format=auto[spine_out]
```

The overlay inputs are appended to argv as `-loop 1 -t END -i text-K.png`,
where END is the overlay's absolute window end. The PNG starts at global
t=0, so its local time matches timeline time and the dual fades land on
AT / END-FADE_OUT without shifting. The `-t END` cap terminates the looped
input at the window end — there is no `-shortest` and no `-t END-AT` in this
chain.

### Stream-copy veto

`features.stream_copy: true` is declared, but copying is gated twice:

1. `support.py` sets the `stream_copy` feature only when a real probe
   confirms the single visual clip is a whole-source h264/yuv420p match
   (duration, resolution, fps, time base — never registry metadata alone).
2. `build_filter_graph` additionally requires no text overlays plus at=0,
   from=0, full duration, same resolution/fps, and no visual adjustments.

`run.py` only forwards `stream_copy_allowed` from the support report — the
veto lives in support features and the command builder, not in a third
`run.py` branch.

## Testing

- Unit + argv tests (`tests/packs/rendering/test_ffmpeg_text.py`): raster
  helpers (fail-closed fonts, color/shadow parsing, wrap/anchor, fades not
  baked into the PNG), the pure argv builder (overlay chain, `-t END` cap,
  stream-copy veto), and support semantics (text `from`, windows,
  color/shadow parity).
- Live smoke (`test_live_media_plus_text_smoke`) observes the overlay window
  on a real render: a 4s constant-color lavfi plate + sine audio + one text
  clip (window [1, 2], fades 0.2/0.2). Guards: ffprobe reports a finite
  duration ≤ 4.5s (hang guard — the overlay input terminates at END);
  MID-WINDOW ink at t=1.5 lifts luma max far above the plate (visible text,
  sampled mid-window, not at window start); after END (t=2.6) luma matches
  the pre-AT plate — mean within ±8 and no bright ink left — with encoder
  noise allowed (no pixel-identity, no checksums). The intro storyboard is
  not the smoke target.

## Explicitly out of scope

Transitions between media clips, media visual effects, per-clip x/y media
transforms, and any font-management subsystem (no font downloading,
embedding, or face discovery). Renderer selection remains explicit and
qualified; there is no planner or selector translation layer.
