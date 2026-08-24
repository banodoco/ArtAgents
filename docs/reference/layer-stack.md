# Layer Stack — `rendering.layer-stack` and `rendering.ffmpeg-compositor`

**Status**: active (epic: Layer Stack, 2026-08-14)
**Scope**: The opt-in `rendering.layer-stack` planner — which routes visual
tracks to renderer-owned z-layers — and the `rendering.ffmpeg-compositor`
finalizer that composites those layers bottom→top. It does **not** replace
`rendering.legacy_hybrid` or `rendering.threejs-hybrid` (those split in
*time*, not z). It is not the default planner.

## What it is

A layer is one renderer-owned contiguous visual-track range, stacked in z,
composited once. The timeline already stores the stack. Layer Stack opens
the render contract just enough that renderers can occupy different z
planes of the same window.

**One-sentence model:** `RenderSegment.layer` is an optional `LayerRef`;
the plan tiles in time *per z*; cross-z overlap is stacking; the compositor
does one bottom→top `overlay` pass; today's concat path is unchanged when
there is only one layer.

```
timeline.tracks[]  ──paint──►  first visual = TOP (unchanged)
        │
        ▼
 rendering.layer-stack
   1. any renderer supports the full visual stack?
        → one segment, layer=None, pin ffmpeg-finalizer     ← FAST PATH
   2. else claim each visual track via registry support(),
      greedy-merge adjacent tracks won by the same renderer,
      emit one full-window segment per layer,
      pin rendering.ffmpeg-compositor
        │
        ▼
 service renders N segments independently
   _window_timeline keeps only layer.tracks
   z>0 stamps metadata.astrid_layer.alpha; renderer skips theme bg
        │
        ▼
 ffmpeg-compositor
   dst = bottom (opaque)
   for src in layers by z: dst ← overlay(src, dst, opacity)
   mux audio from the owning (usually bottom) artifact
   H.264 yuv420p AAC → public .mp4
```

## Direct use

```python
from astrid.sdk.rendering import render

published = render(
    timeline_path="timeline.json",
    assets_registry_path="assets.json",
    out_path="stacked.mp4",
    backend="rendering.layer-stack",
)
```

`render(..., backend="rendering.layer-stack")` is opt-in. Two outcomes:

| Path | When | Plan | Finalizer |
|---|---|---|---|
| **Fast path** | Any eligible renderer `support()`s the full visual stack | One segment, `layer=None` | `rendering.ffmpeg-finalizer` (concat) |
| **Layer path** | No renderer owns the whole stack | One full-window segment per z-layer, each with a `LayerRef` | `rendering.ffmpeg-compositor` |

A remotion-capable text+media timeline takes the fast path — remotion owns
the whole stack, so there is nothing to composite. To force a split, the
registry must lack a full-stack winner (for example, only `rendering.threejs`
+ `rendering.ffmpeg` are eligible: text → threejs, media → ffmpeg).

The planner fails closed on `blendMode` other than `"normal"`, track
opacity outside `(0, 1]`, and visual tracks no eligible renderer can claim.
A non-normal blend is escaped only by the full-stack fast path (the
winning renderer owns the composite internally).

## The z / alpha contract

Paint order is unchanged: **the first visual track in `timeline.tracks` is
TOP**. The planner assigns `z=0` to the last visual track (bottom) and
increments toward the first (highest z = top).

| Layer | Stamp | Segment output |
|---|---|---|
| `z = 0` | `astrid_layer` present, `alpha: false` | Opaque (H.264 / theme background allowed) |
| `z > 0` | `astrid_layer.alpha: true` | Transparent ProRes 4444; renderer skips the theme background |

The stamp is also the public output-admission authority. A direct SDK render
or canonical `timelines render` call may select a `.mov` basename only when
the resolved timeline contains the exact `metadata.astrid_layer.alpha: true`
stamp. With no explicit profile Astrid selects the truthful MOV/ProRes
4444/`yuva444p12le` + PCM S16LE 48 kHz stereo profile. If a profile is
supplied, those mux fields must match. Ordinary timelines continue to use
`.mp4`; an unstamped `.mov` request is rejected before a managed run is
admitted.

For a version-pinned canonical layer:

```bash
python3 -m astrid timelines render top-layer \
  --project demo --expected-version 3 \
  --backend rendering.remotion --output-name top-layer.mov --json
```
| `layer is None` | no stamp | Fast-path opaque segment; concat, not composite |

The host (`RenderService._segment_request`) stamps the metadata and
restricts the materialized timeline to `layer.tracks`. Dispatch,
provenance, `FinalizeRequest` 1:1, and `output_name` are unchanged.

`LayerRef`:

```python
@dataclass(frozen=True)
class LayerRef:
    z: int                      # 0 = bottom; tiling key
    tracks: tuple[str, ...]     # visual track ids this layer owns
    blend: str = "normal"       # v1: only "normal"
    opacity: float = 1.0        # compositor applies aa=
```

Every segment on a layered plan has a `LayerRef`, or none do. Mixing
implicit and explicit z is rejected. Same-z overlap is still illegal;
cross-z overlap is the feature.

## The compositor

`rendering.ffmpeg-compositor` is a finalizer, not a renderer. It accepts
only plans with `layer` set on every segment, at least two distinct z
values, and `blend == "normal"`. Unequal layer lengths are accepted.

Filtergraph, z ascending:

1. A full-length black `color` base lasts `plan.total_frames` (never the
   sum of per-layer durations).
2. Each layer is scaled/padded to the plan canvas, `fps`+`setpts` aligned.
3. `overlay=0:0:format=auto:eof_action=pass` — straight alpha, no
   `alpha=premultiplied`. When a short layer ends, the chain below (or
   the black base) shows through; `repeat` would freeze a dead layer.
4. `opacity < 1` is `colorchannelmixer=aa=`.
5. Audio is taken from the lowest-z `RENDERED` artifact, otherwise
   synthesized `anullsrc`. Overlay audio is discarded.
6. Output is the public container: H.264 `yuv420p` + AAC MP4.

`support()` rejects `layer=None` (concat stays the only consumer of
unlayered plans), `blend ≠ normal`, fewer than two distinct z values,
and duplicate z. Intra-layer time-slicing is allowed by the contract and
unused in v1.

## Alpha codec truth

Stamped remotion and threejs layers emit **ProRes 4444**
(`prores` / `yuva444p12le` in a `.mov`), not VP9. Remotion 4.0.509 does
**not** emit an alpha plane with `--codec=vp9`. The compositor still
forces `-c:v libvpx-vp9` on any VP9 alpha input because the native VP9
decoder drops the plane; ProRes decodes with alpha intact.

Unstamped (default) remotion/threejs output remains opaque H.264/AAC.
`remotion.config.ts` stays jpeg. The alpha path is stamp-only.

## Blend modes

v1 is src-over + alpha only. `LayerRef.blend` exists and accepts only
`"normal"`. `track.blendMode ≠ normal` fails the layer path. Multiply,
screen, and the unused schema blend modes are not consumed. Clip-level
`blendMode` and clip `opacity ≠ 1` stay renderer-rejected.

## Performance

N layers = N independent segment renders + one composite. The service
already renders segments independently; parallelizing those renders is
left for later. The compositor is one ffmpeg process. Do not make
layer-stack the default planner — a remotion-capable timeline is cheaper
on the concat fast path (one render, no overlay).

## Explicit v1 exclusions

Layer Stack deliberately does **not** support, in v1:

- AE blend-mode matrix, track mattes, nesting, adjustment layers
- Clip-level `blendMode`; clip `opacity ≠ 1`
- Combining temporal hybrid + spatial stack in one planner
- Intra-layer time-slicing (the contract allows it; the planner and
  compositor emit/consume one full-window segment per z)
- Making `rendering.layer-stack` the default planner
- Replacing `rendering.legacy_hybrid` / `rendering.threejs-hybrid`
- Hyperframes alpha; distributed / Ray layer DAGs
- CSS `mix-blend-mode` / remotion-internal inter-engine composite
- Spatially mixed audio; background-as-track
- A cap at 2 layers (N>2 is a loop; the first product is usually 2)

## Provenance identity

A layer-path sidecar reports:

- `routing.resolved_policy.planner` → `rendering.layer-stack`
- `routing.resolved_policy.finalizer` → `rendering.ffmpeg-compositor`
- `segments_v2[]` with `layer: {z, tracks, blend, opacity}` and the
  real renderer id (`rendering.threejs`, `rendering.ffmpeg`,
  `rendering.remotion`, …)
- backend fragments for every segment renderer plus
  `rendering.ffmpeg-compositor` (`layer_count`, per-layer z/alpha,
  `audio_source_z`)

A fast-path sidecar looks like any other single-renderer concat:
`layer` is omitted from the segment, and the finalizer is
`rendering.ffmpeg-finalizer`.

## Related Documents

- [threejs-renderer.md](threejs-renderer.md) — `rendering.threejs` and
  the temporal `rendering.threejs-hybrid` planner
- [render-adapter.md](render-adapter.md) — Remotion adapter install
- [sdk.md](sdk.md#rendering-sdk) — Public rendering SDK (`render`, `support`)
- [render-backend-v1.md](../contracts/render-backend-v1.md) — Protocol-v1
  pluggable renderer contract, including optional `LayerRef`
- [env-vars.md](env-vars.md) — Canonical `ASTRID_*` reference
- `astrid/packs/rendering/planners/layer_stack/run.py` — Planner
- `astrid/packs/rendering/finalizers/compositor/run.py` — Compositor
