# Oracle Batch 4 — mechanical fact extract (alpha codec + compositor + naming)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: 2a2ba6b8 (Flash executor). Parent: 73895d25.
Read-only. Do not edit files. Cite file:line. <450 words.

HOST-PROBED (treat as fact; do not re-render):
- Remotion 4.0.509 `--codec=vp9 --pixel-format=yuva420p` → webm, vp9, pix_fmt **yuv420p, NO alpha**.
- Remotion 4.0.509 `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png` → .mov, pix_fmt **yuva444p12le, alpha PRESENT**.
- Remotion rejects `.mp4` output names with `--codec=vp9` (needs .webm). Assume same class of rejection for `--codec=prores` (.mov).

## Do this

1. `git diff 73895d25..2a2ba6b8 --stat`. List every path. Flag anything outside remotion/threejs backends, `_shared`, `ThreeTimelineComposition.tsx`, the two backend test files.

2. Quote (file:line) from `astrid/packs/rendering/backends/remotion/run.py` + `_shared/__init__.py`:
   - How `astrid_layer.alpha` is read.
   - Exact CLI flags appended when stamped.
   - Declared profile fields when stamped (container/codec/pix_fmt/audio/time_base).
   - Whether output_name is rewritten (.mp4→.webm/.mov) or passed through.

3. Quote from `remotion/src/ThreeTimelineComposition.tsx` the background-skip. Confirm it is gated only on `metadata.astrid_layer.alpha === true`. Confirm unstamped still paints `<color attach="background">`.

4. Compositor `astrid/packs/rendering/finalizers/compositor/run.py`:
   - `_layer_has_alpha` exact conditions (quote).
   - When `-c:v libvpx-vp9` is inserted (must be `alpha AND vp9` only?).
   - Per-layer `format=yuva420p` prepend: any codec check, or any alpha?
   - Does anything reject `.mov` / `.webm` / non-mp4 paths? Quote `_safe_protocol_output_path` and layer.path usage.
   - Would a ProRes yuva444p12le .mov already be treated as alpha and decoded with the native decoder (no libvpx)? Yes/no + lines.
   - How many lines would change to ALSO accept ProRes .mov (probe-based decoder: force libvpx only for vp9; treat startswith yuva as alpha)? Estimate: 0 / 1-10 / 10-30 / more.

5. Segment naming:
   - `astrid/core/rendering/service.py` where `output_name=f"segment-{index:04d}.mp4"` is set. Quote.
   - Does the renderer MUST write exactly `request.output_name`, or can RenderResult.video.path be a different basename? Quote the service check (artifact path vs request.output_name).
   - `_OUTPUT_NAME_RE` / `validate_output_name`: do `.mov` and `.webm` already pass? Quote the regex.
   - Tasklist forbids changing `validate_output_name`. Can a one-line service change to `segment-NNNN.mov` for alpha segments happen in B4 rework / B5 without touching the validator?

6. Tests in the 2a2ba6b8 diff: list new test names + what each asserts. Note the 3 known failures + 1 xfail (from `.oracle/findings/batch-4-exec.txt`) — map each to a file:line assertion.

Do not run remotion/pytest. Print-only python ok.

## Report shape

```
SCOPE: clean|dirty — paths
STAMP: how alpha is read
FLAGS: exact argv extras
PROFILE: declared fields
BG-SKIP: gated? unstamped intact?
COMPOSITOR-ALPHA: conditions
COMPOSITOR-DECODER: libvpx only if ...
COMPOSITOR-MOV: accept-already | needs-N-lines
NAMING: service hardcodes .mp4? backend rewrite? validator allows .mov/.webm?
PATH-BIND: result path must == request.output_name? Y/N + line
TESTS: name → assert
FAILURE-MAP: 3 fails + xfail → why
```
