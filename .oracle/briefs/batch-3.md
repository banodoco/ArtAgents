# Megado Batch 3 — rendering.ffmpeg-compositor (Layer Stack)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan` (branch `layer-plan`, HEAD cf947761). Execute ONLY this batch. Do NOT broaden scope. Do NOT edit contracts.py/service.py/packs. Do NOT run the full test suite or formatters. Oracle gates the result.

Environment: `PYENV_VERSION=3.11.11`. FFmpeg/ffprobe present. This is pure Python + ffmpeg — no node.

## Context — read FIRST

- `.oracle/plan.md` (Batch 3 section) + `.oracle/tasklist.md`.
- Batches 1-2 (d5b960d7, fe7622c7, dce60b9f): RenderSegment.layer (LayerRef: z, tracks, blend="normal", opacity) + per-z cursor + track-filtered host slice + `metadata.astrid_layer = {z, alpha}` stamp.
- **Oracle note (binding): "B3 compositor must pad short layers (incl. z=0); do not assume an opaque full-span bottom."** Any layer may cover only part of the timeline. The compositor pads each layer to the plan window (background/transparent fill) and composites bottom→top.
- The existing finalizer pattern: `astrid/packs/rendering/finalizers/ffmpeg/run.py` (finalize/support/main, _PreparedSegment, preflight). Mirror its protocol + result shape.

## Goal

New finalizer `rendering.ffmpeg-compositor`: merges N layer segments (possibly overlapping in time, ordered by z) into ONE output video via ffmpeg `overlay` filtergraph, bottom→top, with per-layer padding, straight-alpha compositing, and the plan's canonical frame count.

## Reference — the ffmpeg overlay recipe (from swarm finding 05)

- Alpha input (top layers): WebM/VP9 + `yuva420p`. **ALWAYS `-c:v libvpx-vp9` on alpha inputs** (native VP9 decoder drops alpha).
- `overlay` expects STRAIGHT alpha by default; do NOT pass `alpha=premultiplied`.
- Chained: `[0:v][1:v]overlay=...:format=auto[l1]`, `[l1][2:v]overlay=...[l2]`, ... in z order.
- Per-layer opacity (v1: only needed if opacity < 1): `format=rgba,colorchannelmixer=aa=<op>` before overlay.
- Per-layer padding: `scale=<W>:<H>,setsar=1,fps=<fps>,setpts=PTS-STARTPTS` + pad to canvas (each layer may be shorter than the plan window: `tpad=stop_mode=clone` or pad with transparent/black to the full length).
- Output: H.264 yuv420p + AAC (the plan's canonical profile), `-movflags +faststart`.
- Background: `color=c=<bg>:s=<W>x<H>:r=<fps>` as input [0] when there's no full-span bottom layer (or always — a color base is simplest and correct per the oracle note: pad short layers, don't assume a bottom).

## Implementation

### 1. `astrid/packs/rendering/finalizers/compositor/` (new dir)
- `__init__.py` (empty)
- `finalizer.yaml`:
```yaml
schema_version: 1
id: rendering.ffmpeg-compositor
name: FFmpeg Layer Compositor
version: 1.0.0
protocol_version: 1
command: [python3, run.py]
operations: [finalize, support]
description: Composite overlapping z-layer segments bottom-to-top into one timeline-length video.
capabilities:
  containers: [mp4]
  audio_ownership: [rendered, none]
  features:
    layer_compositing: true
    straight_alpha: true
    short_layer_padding: true
required_permissions: [project_files, subprocess]
required_binaries: [ffmpeg, ffprobe]
```
- `run.py`: mirror the existing finalizer's `support(request, workspace)` + `finalize(request, workspace)` + `main()` protocol (read FinalizeRequest JSON via `--request`, write result JSON via `--result`). Look at the existing ffmpeg finalizer's main() for the exact wire protocol.

### 2. Compositor logic (finalize)
1. **Validate**: every segment MUST have `layer` set (layer=None segments are the concat finalizer's job — compositor support() rejects a plan with any layer=None segment or <2 distinct z layers); every `blend` must be "normal" (v1); `window` must be the FULL plan window per layer (v1 emits one segment per z covering the plan window — but per the oracle note, ACCEPT shorter layers and pad them; the checkpoint test uses synthetic full-window segments; the real stacked render in B6 may have a short top layer).
2. **Frame-count authority**: output = `plan.total_frames` (NEVER `sum(segment.window.duration_frames)` — overlapping layers double-count).
3. **Profile**: use the plan's canonical profile (width/height/fps/time_base/h264/aac/yuv420p).
4. **Filtergraph assembly** (ordered by layer.z ascending):
   - base: `color=c=<plan background or black>:s=WxH:r=fps:d=<total_seconds>`
   - per layer: `-i <segment.mp4>`, then `[N:v]scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=FPS,setpts=PTS-STARTPTS[tN]` (pad to canvas), if alpha (metadata said alpha or probe shows yuva) `format=yuva420p` first; if opacity < 1 `format=rgba,colorchannelmixer=aa=<op>`; then `[prev][tN]overlay=0:0:format=auto[outN]`.
   - Handle SHORT layers: if a layer's segment duration < plan duration, the `color` base + `overlay` naturally leaves the rest showing the base (overlay only paints where the input has frames) — verify this is true, or add `tpad=stop_mode=clone:stop_duration=<remaining>` to extend. The oracle note says pad short layers; ensure the output length = plan.total_frames regardless.
   - Audio: take audio from the segment with the LOWEST z that has an audio stream (usually z=0); if none, synthesize silent AAC. Map audio through with `-map` on the chosen input.
5. **Result**: mirror the existing finalizer's result shape (video artifact + profile + duration_frames = plan.total_frames + audio_ownership + backend_fragments with the compositor id). Probe the output with ffprobe to confirm h264/yuv420p/aac/frame-count.
6. **support()**: reject plans with any layer=None segment, any blend != "normal", <2 distinct z layers, or a profile missing canvas/fps. Honest reasons.

### 3. Register in `astrid/packs/rendering/pack.yaml`
Add `- finalizers/compositor/finalizer.yaml` under `extensions.rendering.finalizers`.

### 4. Tests — `tests/packs/rendering/test_ffmpeg_compositor.py`
- support(): accepts a 2-layer plan; rejects layer=None plans, single-layer plans, blend != normal.
- Synthetic composite: build 2 tiny segments with ffmpeg — bottom = opaque color (e.g. red, full window), top = a small opaque shape on transparent (e.g. a green 20x20 box on yuva420p, full window) — run the compositor, ffprobe output: h264, yuv420p, aac, frame count == plan.total_frames, and PIXEL PROOF: the green box region is green (top painted over red), a region outside the box is red (bottom shows through).
- Short top layer: bottom full-window red + top only [0, half) transparent-with-green → output full length, green visible in first half, red in second half (the oracle note's padding requirement).
- Zero-alpha top layer: top is fully transparent → output = bottom only.
- Frozen: the existing `rendering.ffmpeg-finalizer` concat tests must still pass (unchanged).

## Do NOT do (LEAVE)
- No contracts.py/service.py edits (the finalizer just reads plan.segments[].layer).
- No changes to the existing concat finalizer.
- No blend modes beyond "normal" (overlay only), no premultiplied alpha.
- No changes to remotion/threejs (batch 4).

## Verification
```bash
PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_ffmpeg_compositor.py tests/packs/rendering/test_ffmpeg_finalizer.py tests/core/rendering/test_freeze.py
PYENV_VERSION=3.11.11 python scripts/reshape/compare_ruff_baseline.py   # <= 1469
```
Update test_freeze.py ONLY for the new finalizer id set (the frozen exact-surface test will fail — add `rendering.ffmpeg-compositor`).

Commit: `megado: batch 3 — rendering.ffmpeg-compositor (overlay merge, short-layer padding, frame-count authority)`.

## Report
<400 words: the filtergraph assembly, how short layers pad, the pixel-proof evidence (ffprobe + extracted-frame colors), frame-count authority proof, test counts, freeze update, commit sha, git status. Evidence-first.
