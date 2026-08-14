# Oracle Batch 6 — mechanical fact extract (Layer Stack finale)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: c87cc49f (host-committed; Grok executor timed out). Parent: 46af2451.
Read-only. Do not edit files. Cite file:line. <500 words.

Do this first:
```
git show --stat c87cc49f
git diff 46af2451..c87cc49f --stat
git diff 46af2451..c87cc49f -- astrid/core
git diff 46af2451..c87cc49f -- tests/core/rendering/test_schema_contract.py
git log -1 --format='%H %s' c87cc49f
```

Primary files:
- `tests/core/rendering/test_layer_stack.py`
- `tests/packs/rendering/test_ffmpeg_compositor.py`
- `astrid/packs/rendering/run.py`
- `astrid/packs/rendering/planners/layer_stack/run.py`
- `docs/reference/layer-stack.md`
- `docs/contracts/render-backend-v1.md`
- `tests/core/rendering/test_package_data.py`
- `tests/packs/rendering/test_builtin_registration.py`

Print-only python / git / grep ok. Do not run pytest, remotion, or ruff.

## Do this

1. SCOPE. List every path in `46af2451..c87cc49f`. Flag ANY edit in:
   - `astrid/core/**` (must be empty this batch)
   - `tests/core/rendering/test_schema_contract.py` (must be empty)
   - remotion / gen_remotion_types.py / hybrids
   Anything outside tests, docs, pack `run.py`, compositor tests, planner (dead-field delete), package-data/registration?

2. DISPATCHER. In `astrid/packs/rendering/run.py`, quote the new compositor route.
   - Exact id matched? `rendering.ffmpeg-compositor`?
   - What function does it call? Same pattern as existing finalizer (`rendering.ffmpeg-finalizer`)?
   - What happens to unmatched ids (fallthrough to remotion)? Could compositor have been mis-routed before?
   - Does the new branch shadow / break the existing finalizer or planner branches? Quote the if/elif order.

3. DEFERRED ITEMS. For each, quote the test name + the exact assertion:
   - compositor short-bottom: does z=0 (bottom) end early and the test assert the BASE shows in the tail (not black, not frozen last frame of bottom)?
   - layer-stack merge-reject: ffmpeg 2 adjacent media → re-support rejects so they stay split? How is ffmpeg's one-visual-track rule exercised?
   - opacity → LayerRef: what opacity is set and what is asserted on the emitted LayerRef?
   - zero-alpha-top: what is asserted?
   - `_LayerClaim.timeline` removed: confirm the field is gone and no remaining reads.

4. DOCS. Read `docs/reference/layer-stack.md` and the new `render-backend-v1.md` section.
   For each claim, YES/NO + cite the shipped code that matches or contradicts:
   - z contract (first visual = highest z = top)
   - ProRes-alpha only for z>0 stamp; z=0 opaque
   - blend deferred (src-over + alpha only)
   - remotion-capable full stack still concat / layer=None
   - perf note (if any)
   Any doc claim that is false or stale vs code?

5. MANIFESTS. What did `test_package_data.py` and `test_builtin_registration.py` add? Do they cover planner AND compositor (wheel / registration)?

6. REVERT. Host says an out-of-scope `gen_remotion_types.py` change was reverted. Confirm that file is NOT in `c87cc49f`. `git show c87cc49f --stat` must not list it.

## Report shape

```
SCOPE: clean|dirty — path list + core/schema/remotion status
DISPATCH: id= dest= elif-order= fallthrough-before= break-finalizer?
SHORT-BOTTOM: test= what-asserted= base-shows-in-tail?
MERGE-REJECT: test= how= ffmpeg-split?
OPACITY: test= LayerRef.opacity=
ZERO-ALPHA: test= asserted=
DEAD-FIELD: timeline-gone? Y/N
DOCS: z= ProRes= blend= concat= perf= false-claims=
MANIFESTS: planner? compositor?
REVERT: gen_remotion_types absent from commit? Y/N
GAPS: acceptance not covered
```
