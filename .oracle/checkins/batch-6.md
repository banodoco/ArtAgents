# Checkpoint 6 — Batch 6 (Layer Stack FINALE) — PASS

Oracle: Grok 4.6. Delegated Flash facts + proof + critique
(`.oracle/findings/oracle-b6-{facts,proof,critique}.txt`). Host
re-checked cited lines. Scope diffs independently empty.

**Epic COMPLETE. Merge to main may proceed.**

## Delegated evidence

- Facts: `.oracle/findings/oracle-b6-facts.txt` (scope, dispatcher, deferred, docs, manifests, revert)
- Proof: `.oracle/findings/oracle-b6-proof.txt` (HONESTY: PARTIAL — real pipeline, planner verb injected)
- Critique: `.oracle/findings/oracle-b6-critique.txt` (lean; no blocker)

## Acceptance

**Real stack.** `test_real_stacked_render_constructed_plan_threejs_over_remotion`:
real threejs ProRes + real remotion + real composi**PASS** — epic COMPLETE. Merge to main may proceed.

Delegated Flash: `.oracle/findings/oracle-b6-{facts,proof,critique}.txt`. Host re-checked cited lines.

**Real stack is real, plan verb is injected.** `test_real_stacked_render_constructed_plan_threejs_over_remotion` runs live threejs ProRes, remotion, and ffmpeg-compositor through `RenderService`/`sdk_render`. `_InjectPlanTransport` intercepts only `verb=="plan"` + `rendering.layer-stack`; everything else is `CommandTransport`. The plan is a real `layer_stack.plan` (threejs+ffmpeg) with ffmpeg relabeled remotion — `__post_init__` re-runs; stamp `alpha: z>0` and track slice still fire. Pixel proof (frame 0): corner (4,4) media-red + ≥1 non-red in the text band. 24f h264/420p + aac. Flash: HONESTY PARTIAL — planner would never emit this assignment with remotion registered (fast path). Disclosed; tasklist asked for a real 2-layer render, not planner-driven remotion-bottom.

**Dispatcher.** Exact `rendering.ffmpeg-compositor` before finalizer/ffmpeg/remotion-else. Pre-fix fallthrough was remotion (real gap). Distinct-id equality; finalizer unbroken.

**Deferred.** Short-bottom: 5f red under 10f green; f8 (50,50)==black (`eof_action=pass`). Merge-reject: two ffmpeg media tracks stay two segments. Opacity 0.4 → `LayerRef`. `_LayerClaim.timeline` gone.

**Docs / scope / gate.** `layer-stack.md` matches z, ProRes-for-`z>0`, blend deferred, concat fast path, perf. `46af2451..c87cc49f`: 8 paths. `astrid/core` empty. `test_schema_contract.py` empty. `gen_remotion_types.py` absent (revert correct). Host: 782 passed / 1 pre-existing env fixture; ruff ≤1469; remotion-typecheck; renderer-parity 18.

**Elegance.** Lean. Dead `top_opacity` knob and duplicate `_frame_rgb` are nits, not defects.
