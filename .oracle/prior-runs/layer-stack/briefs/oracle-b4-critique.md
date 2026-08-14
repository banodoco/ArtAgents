# Oracle Batch 4 — elegance critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit 2a2ba6b8. Read-only. Take a position. <300 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not implement.

USER GOAL: "stack renderers, transparent or not." Opaque stacking already works (compositor overlay). True transparency is the nice-to-have, but Batch 4's checkpoint is "stamped = alpha plane; text-only corner alpha == 0."

HOST FACTS (do not re-litigate):
- VP9/webm in Remotion 4.0.509: NO alpha.
- ProRes 4444: YES alpha (`yuva444p12le`).
- Three.js bg-skip (omit `<color attach="background">` when stamped) is the mechanism that makes the ProRes alpha plane actually transparent (otherwise corners are opaque bg).
- Compositor (B3, PASSED) forces `libvpx-vp9` only when `alpha AND vp9`; already treats `pix_fmt startswith yuva` as alpha; overlay via `format=yuva420p`.

Options the oracle must pick:
- (a) REWORK 2a2ba6b8: stamped-alpha remotion/threejs emit ProRes 4444 `.mov` (declared prores/yuva444p10-or-12le/mov); keep threejs bg-skip; compositor accepts prores via existing yuva probe (tiny decoder tweak only if needed). Reject vp9 for alpha segments.
- (b) KEEP vp9 flags + declared yuv420p; opaque remotion/threejs tops; defer remotion transparency; ffmpeg-native tops only.

Recommend (a) if compositor change is small (probe-based decoder). Else (b).

Also judge:
1. KEEP the stamp-consumption + bg-skip even if flags change? Or revert until an engine emits alpha?
2. Does `.mov` naming need a service `segment-NNNN.mov` change (service.py hardcodes `.mp4`), or can compositor just accept whatever path the artifact has? Remotion rejects `.mp4` with these codecs.
3. Tasklist said "don't change output_name". That assumed VP9-in-.mp4. Is revising that constraint justified?

## Report shape

```
PATH: a|b — one-sentence why
COMPOSITOR: zero-change | tiny-probe | large — ...
KEEP-STAMP: keep|revert — ...
NAMING: service-ext-change | compositor-already-ok | both — ...
CONSTRAINT: revise-output_name | keep-mp4-filename — ...
BATCH5-ASSUME: what the planner must assume about remotion/threejs as top-layer engines
MUST-FIX-NOW: numbered issues for the B4 rework (file-level)
YAGNI-CUT: anything in 2a2ba6b8 to delete
```
