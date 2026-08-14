# Checkpoint 5 — Batch 5 (Layer Stack planner) — PASS

Oracle: Grok 4.6. Delegated Flash facts + z-contract + critique
(`.oracle/findings/oracle-b5-{facts,z,critique}.txt`). Host
re-checked cited lines. Host pytest (tasklist verify) → **71 passed**.

**Batch 6 may start.**

## Delegated evidence

- Facts: `.oracle/findings/oracle-b5-facts.txt` (scope, fast path, claim, merge, fail-closed, profile, recursion, tests)
- Z-contract: `.oracle/findings/oracle-b5-z.txt` (paint order, stamp, compositor)
- Critique: `.oracle/findings/oracle-b5-critique.txt` (KISS/YAGNI; no blocker)

## Acceptance

**Scope** (`f9f8c120` vs `954d9664`): 7 paths. Planner dir + `pack.yaml` +1 + pack `run.py` dispatch branch + `test_layer_stack.py` + freeze id only. Hybrids / core / backends / finalizers byte-untouched.

**Fast path** (`run.py:250–270`, `573–614`): first eligible candidate whose real `support()` accepts the FULL timeline (`_first_supporting` → `_probe_support` → injected resolver or `_CommandSupportResolver`). Not a heuristic. Winner emits one `RenderSegment` with no `layer=` (`layer is None`) + `rendering.ffmpeg-finalizer`.

**Layer path** (`299–399`, `616–685`): per-track `_project_tracks` → `_component_timeline`; first supporting candidate; greedy merge only if same renderer AND same opacity AND winner still `support()`s the merged projection. ffmpeg `exactly one visual track` (`backends/ffmpeg/support.py:283`) therefore keeps adjacent media sp**PASS. Batch 6 may start.**

Delegated Flash: `.oracle/findings/oracle-b5-{facts,z,critique}.txt`. Host re-checked cited lines. Tasklist suite: **71 passed**.

**Routing.** Fast path is real `support()` on the full timeline (`run.py:250–270`), not a heuristic. Else per-track `_project_tracks` + first claimant. Merge only if same renderer, same opacity, **and** the winner still `support()`s the merged projection — ffmpeg’s one-visual-track rule therefore keeps adjacent media split.

**Fail-closed.** `blendMode≠normal`, opacity outside `(0,1]`, no claimant: all `RendererUnsupportedError`, track named. Blend is layer-path only; remotion full-stack still escapes (correct, tested).

**Profile.** Every probe is `profile=None` (`273–296`). `_CommandSupportResolver` materializes the projection and clears the window. Plan profile stays canonical h264/yuv420p/mp4. B5 note honored.

**Z contract — OK, not inverted.** First visual track = TOP = highest z. Service stamps layered segments with `alpha: z > 0` (`service.py:1091–1100`). z=0 is stamped but opaque; z>0 is ProRes. Compositor sorts z ascending (`compositor/run.py:586`); highest z overlays last. Fast path is `layer=None` (no stamp), not `z=0`. Forced split: overlay z=1/threejs/alpha, source z=0/ffmpeg/opaque.

**Scope.** 7 paths. Hybrids / core / backends / finalizers untouched. Freeze +1 planner id. Planners excluded from candidates. Opt-in via qualified id only.

**Elegance.** 772 lines is peer-sized. Re-support is the right merge check. Dead `_LayerClaim.timeline` (written, never read) is YAGNI, not a defect. Missing tests (opacity, ffmpeg merge-reject) are insurance, not blockers.
rge-reject, planner-id filter) are insurance, not blockers — same class as B3’s deferred short-bottom pixel test.

**Host:** `pytest -q tests/core/rendering/test_layer_stack.py tests/core/rendering/test_threejs_hybrid.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_freeze.py` → **71 passed**.
