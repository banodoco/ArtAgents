# Megado Batch 4 REWORK — ProRes 4444 alpha (Layer Stack)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan` (branch `layer-plan`, HEAD 73895d25). The oracle reviewed Batch 4 and mandated path (a): REWORK the alpha output from vp9 (which emits NO alpha in remotion 4.0.509) to **ProRes 4444** (which the host probed emits `yuva444p12le` — real alpha). Execute ONLY these fixes. Do NOT broaden scope. Oracle re-gates.

Environment: `PYENV_VERSION=3.11.11`; `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"`. Real renders needed.

## The probed truth (binding)

- vp9/webm in remotion 4.0.509: `pix_fmt yuv420p` — **NO alpha**. Dead path.
- ProRes 4444: `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png` → `pix_fmt yuva444p12le` — **real alpha plane**. This is the alpha path.
- ProRes rejects `.mp4` output names (remotion requires `.mov`). The service hardcodes `segment-NNNN.mp4` (service.py:1362) — so the BACKEND must remap the output extension when stamped.
- The compositor (batch 3) already handles `yuva*` inputs (compositor/run.py:345 alpha detection; native ProRes decode; `libvpx-vp9` only for vp9 inputs). **Zero compositor change needed.**

## The fixes (from the oracle verdict)

### 1. Remotion backend (remotion/run.py) — ProRes flags + profile + .mov remap

When `metadata.astrid_layer.alpha == true` (the stamp):
- CLI flags: replace `--image-format=png --pixel-format=yuva420p --codec=vp9` with `--image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444`.
- Output naming: remap the requested output to `.mov` (e.g. if `request.output_name` is `segment-0000.mp4`, render to `segment-0000.mov`) — but the RESULT artifact path/provenance must stay consistent (the compositor reads artifacts by path; check how the finalizer/transport resolve artifact paths — the artifact's declared path must point at the actual .mov file).
- Declared profile when alpha: **probed truth** — container mov, codec prores, pix_fmt yuva444p12le (or yuva444p10le — PROBE a real render and declare exactly what comes out), time_base/audio from the actual artifact (probe: prores time_base? audio? — record it). NOT webm/1/1000/opus (that was the vp9 path).
- Unstamped (alpha absent/false): ZERO change (h264/yuv420p/.mp4 today).

### 2. Theme background neutralization (remotion/src/TimelineComposition.tsx — the DOM composition, NOT just threejs)

The oracle found: `TimelineComposition.tsx:272` paints `theme.visual.color.bg` — the DOM composition's background. Even with threejs's `<color>` skipped, a stamped top layer through the DOM TimelineComposition would still paint opaque bg. The fix: when the stamped metadata says alpha, the serialized theme's `visual.color.bg` must be TRANSPARENT in the props (merged_props) so neither composition paints it. Where does the backend build `merged_props`/theme? (remotion/run.py — find where `theme_for_props` / resolved theme is set; when alpha, set `visual.color.bg` to a transparent value or remove it.) The threejs `<color attach="background">` skip (ThreeTimelineComposition.tsx:432, already committed) stays.

### 3. Tests (test_remotion_backend.py + test_threejs_backend.py)

- The stamped alpha test: output is `.mov` (or the remapped path), ffprobe shows prores + `yuva444p10le|12le`; **corner pixel alpha == 0** (un-xfail the corner assertion — the threejs bg-skip + theme neutralization must make the corner truly transparent).
- threejs dict→RenderRequest: the executor's test called `_protocol_render` with a dict — fix the test to pass a `RenderRequest` (or call through the service).
- The vp9-based declared-profile test: replace with the ProRes profile.
- Frozen unstamped path: unchanged, prove no regression.
- Add one test: stamped top layer via the REAL service path → artifact is .mov/prores with alpha; unstamped → .mp4/h264 opaque.

## Do NOT do
- No compositor changes (it already handles yuva*).
- No service.py/dispatch/validate_output_name changes (the backend remaps; the oracle explicitly froze those).
- No vp9/webm anywhere in the alpha path.
- No changes to the unstamped path.

## Verification
```bash
PYENV_VERSION=3.11.11 PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" python -m pytest -q \
  tests/packs/rendering/test_remotion_backend.py \
  tests/packs/rendering/test_threejs_backend.py \
  tests/packs/rendering/test_remotion_locking.py \
  tests/packs/test_renderer_parity.py
PYENV_VERSION=3.11.11 python scripts/reshape/compare_ruff_baseline.py  # <= 1469
```
Plus ONE real stamped render proof: corner pixel alpha == 0 (extract frame 0, PIL assert alpha at all 4 corners == 0), and ffprobe showing prores/yuva.

Commit: `megado: batch 4 rework — ProRes 4444 alpha output (real alpha plane, .mov, theme bg neutralization)`.

## Report
<400 words: the flag/profile/naming/theme changes, the probed ProRes artifact truth (codec/pix_fmt/time_base/audio), corner-alpha==0 proof, unstamped no-regression evidence, test counts, commit sha, git status. Evidence-first.
