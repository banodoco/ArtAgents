# Megado Batch 4 — Alpha output on remotion + threejs (Layer Stack)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan` (branch `layer-plan`, HEAD 73895d25). Execute ONLY this batch. Do NOT broaden scope. Do NOT edit contracts.py/service.py/planners/finalizers. Oracle gates the result.

Environment: `PYENV_VERSION=3.11.11`; `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` for npm/remotion. The worktree's remotion has node_modules + working chrome (4.0.509 — verified, extract works). This batch needs REAL renders (remotion + threejs) — allow ~2 min per render.

## Context — read FIRST

- `.oracle/plan.md` (Batch 4) + `.oracle/tasklist.md`.
- Batches 1-3 (d5b960d7..edf0859a): contract LayerRef + per-z cursor; track-filtered host slice; `metadata.astrid_layer = {z, alpha}` stamp (batch 2); `rendering.ffmpeg-compositor` (batch 3).
- **This batch consumes the stamp**: when the materialized timeline's metadata says `astrid_layer.alpha == true` (z > 0), the renderer must emit TRANSPARENT output. Unstamped / z=0 → today's opaque output, byte-identical.
- Swarm finding 05 (alpha mechanics): remotion transparent = `--image-format=png --pixel-format=yuva420p --codec=vp9`; threejs needs the `<color attach="background">` removed (R3F Canvas defaults to alpha:true + setClearAlpha(0)).

## The change

### 1. Remotion backend — alpha flags (astrid/packs/rendering/backends/remotion/run.py)

The CLI invocation is at ~run.py:556-568 (`npx remotion render <id> --props ... --output ... --allow-html-in-canvas --enforce-audio-track`).

- Read the materialized timeline's metadata (`astrid_layer.alpha` — the backend already loads the timeline for serialization; find where and thread the flag through).
- When `alpha == true`: append `--image-format=png --pixel-format=yuva420p --codec=vp9` to the remotion CLI args.
- When alpha is absent/false: NO change (today's behavior — jpeg/h264 path, remotion.config.ts stays `setVideoImageFormat('jpeg')`).
- The declared profile must match the alpha output: when alpha, the output is VP9/yuv420p... wait — check: does `--codec=vp9` change the container? Remotion vp9 = webm. The segment artifact's declared profile (in the RenderResult) must match what ffprobe sees (the strict validation in artifacts.py compares profile fields). So when alpha: declared profile should be container webm, codec vp9, pix_fmt yuva420p. When not: h264/yuv420p as today. **Verify with a real render + ffprobe** what the alpha output actually is (container, codec, pix_fmt, time_base) and set the declared profile to match. The compositor (batch 3) decodes with libvpx-vp9 — it expects webm/vp9/yuv420p-with-alpha or similar. **Probe and record the truth.**
- Renderer.yaml: add `features.alpha_output: true` (bool feature, allowed by the manifest schema). Keep everything else.

### 2. Three.js backend — skip background when alpha (remotion/src/ThreeTimelineComposition.tsx + backends/threejs/run.py)

- `ThreeTimelineComposition.tsx`: currently always renders `<color attach="background" args={[background]} />` (:409). When the props (serialized timeline metadata) say `astrid_layer.alpha == true`, OMIT the background color element (R3F Canvas defaults alpha:true, clear alpha 0 → transparent). The background resolution logic stays for the opaque case.
  - How does the composition get the metadata? The serialized timeline's `metadata` dict flows through props (timeline.metadata). Read it in the component and conditionally render the color element.
- `backends/threejs/run.py`: same alpha flag threading as remotion (the threejs backend invokes `_execute_remotion` from remotion — check whether the alpha flags flow through that shared path or need passing; if _execute_remotion is shared, add an alpha parameter, remotion passes it when stamped, threejs passes it when stamped).
- Renderer.yaml: `features.alpha_output: true`.

### 3. The stamp flow (verify it works end-to-end)

The stamp was added by the SERVICE in batch 2 (metadata.astrid_layer on the materialized timeline). The renderer receives the materialized timeline (host-sliced) with `window=None`. Confirm: the backend's timeline load sees the metadata, the composition's props carry it, and the flags/background-skip fire. **A real stacked render path**: bottom layer z=0 (opaque, no stamp change) + top layer z=1 (stamped alpha:true) → top comes out transparent. But the compositor isn't wired to a planner yet (batch 5) — so prove alpha at the SEGMENT level: render a single threejs segment whose materialized timeline has `astrid_layer.alpha: true` stamped (construct the request directly, or via the service with a hand-built layered plan — the service accepts it now) and ffprobe the segment: it must show alpha (vp9/webm, yuva*, or a probe that reveals transparency).

## Do NOT do (LEAVE)
- No changes to the unstamped path (byte-identical today's output — run the frozen remotion/threejs tests to prove).
- No hyperframes alpha (deferred per plan).
- No changes to the compositor/planner/contracts.
- No `remotion.config.ts` change (stays jpeg).

## Verification

```bash
PYENV_VERSION=3.11.11 PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" python -m pytest -q \
  tests/packs/rendering/test_remotion_backend.py \
  tests/packs/rendering/test_threejs_backend.py \
  tests/packs/rendering/test_remotion_locking.py \
  tests/packs/test_renderer_parity.py
PYENV_VERSION=3.11.11 python scripts/reshape/compare_ruff_baseline.py  # <= 1469
```

New tests (in test_remotion_backend.py + test_threejs_backend.py):
1. Unstamped render → opaque (h264/yuv420p) — the frozen path, prove no regression.
2. Stamped alpha render (hand-built layered plan via the service, or direct request with stamped metadata) → ffprobe shows alpha-capable output (record the actual codec/pix_fmt/container).
3. Threejs: stamped → corner pixel alpha == 0 (the B4 checkpoint: "corner alpha == 0" — extract a frame, check the corner is fully transparent). Unstamped → corner == background color.
4. Declared profile matches the probed artifact for BOTH paths (strict validation must pass).

Commit: `megado: batch 4 — alpha output on remotion + threejs (consumes astrid_layer stamp)`.

## Report
<400 words: the exact flag/background changes, the PROBED alpha artifact truth (container/codec/pix_fmt/time_base), declared-profile handling, corner-alpha proof, frozen-path no-regression evidence, test counts, commit sha, git status. Evidence-first.
