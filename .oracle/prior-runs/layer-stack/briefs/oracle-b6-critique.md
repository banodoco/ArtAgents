# Oracle Batch 6 — elegance critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit c87cc49f vs parent 46af2451. Read-only. Take a position. <300 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not implement.

USER GOAL (tasklist Batch 6): one real 2-layer render (ffprobe + pixel proof + sidecar); remotion-only still concat; docs `docs/reference/layer-stack.md` + short `render-backend-v1.md` section; ruff ≤ 1469; wheel contains planner + finalizer. Deferred from earlier oracles: short-bottom compositor pixel test; layer-stack merge-reject + opacity insurance; delete dead `_LayerClaim.timeline`.

Diff is 8 files, +789/−21. Mostly tests + one new doc. Pack dispatcher now routes `rendering.ffmpeg-compositor` (executor says this was a real gap: compositor was not invocable via pack `run.py`). Host reverted an out-of-scope `gen_remotion_types.py` alias-dedup.

Read:
- `git diff 46af2451..c87cc49f`
- `tests/core/rendering/test_layer_stack.py` (new helpers + tests)
- `tests/packs/rendering/test_ffmpeg_compositor.py` (short-bottom)
- `astrid/packs/rendering/run.py` (dispatcher)
- `docs/reference/layer-stack.md`

Judge:

1. `_InjectPlanTransport` + constructed plan: honest test seam, or a second planner? Could they have used a remotion-less registry so the real planner emits the stack (as B5 forced-split does)?
2. Dispatcher compositor route: necessary gap-fill, or scope creep? Does it match existing finalizer dispatch (copy-paste) or invent a new pattern?
3. Test weight: +459 lines in `test_layer_stack.py` — covering the finale, or padded helpers / duplicate fixtures?
4. Docs 201 lines — proportional reference, or essay?
5. Any remaining dead code, speculative hooks, unused helpers after `_LayerClaim.timeline` removal?
6. Anything in the diff that is not Batch 6 (scope creep)?

## Report shape

```
VERDICT-LEAN: lean | padded | over-engineered — one sentence
CUT: numbered things to delete or collapse (file:line)
KEEP: what must stay
INJECT: honest-seam | cheat — ...
DISPATCH: gap-fill | creep — ...
TEST-WEIGHT: proportional | bloated — ...
DOCS: proportional | essay
BLOCKER?: none | numbered issues that are real defects (not style)
```
