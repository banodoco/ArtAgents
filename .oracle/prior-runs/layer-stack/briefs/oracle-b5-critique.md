# Oracle Batch 5 — elegance critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit f9f8c120. Read-only. Take a position. <300 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not implement.

USER GOAL: opt-in planner. Full-stack support → one layer=None + concat. Else per-track claim + greedy adjacent merge → per-layer segments + ffmpeg-compositor. Fail closed on blend≠normal and unsupported tracks. Hybrids untouched.

Executor report: 772-line `run.py` + 506-line tests. Algorithm: candidates(eligible=True); canonical profile for fps/canvas/total_frames only; first visual = TOP; fast path = first candidate whose real support() accepts FULL timeline; else per-track projection + claim; fail closed; merge adjacent same-renderer/same-opacity only if winner still supports merged projection. Profile=None on every support(). Plan profile stays canonical h264.

Read `astrid/packs/rendering/planners/layer_stack/run.py` and `tests/core/rendering/test_layer_stack.py`. Compare size/shape to existing planners under `astrid/packs/rendering/planners/`.

Judge:

1. 772 lines — proportional to the algorithm, or padded? Dead helpers? Duplicate timeline-copy? Over-abstracted classes where functions would do?
2. Would a simpler structure (one function: try full-stack; else claim-per-track; merge; emit) do the same job?
3. Any speculative machinery not required by the tasklist (blend-mode hooks, future planners, config objects, extra protocol types)?
4. Is the re-support() merge check the right complexity, or could they just refuse to merge ffmpeg (one-visual-track) by id? Which is more honest?
5. Tests: 10 tests / 506 lines — covering acceptance, or testing internals?

## Report shape

```
VERDICT-LEAN: lean | padded | over-engineered — one sentence
CUT: numbered things to delete or collapse (file:line)
KEEP: what must stay
MERGE-CHECK: re-support is right | id-special-case is enough
TEST-WEIGHT: proportional | bloated — ...
BLOCKER?: none | numbered issues that are real defects (not style)
```
