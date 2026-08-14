# Oracle Batch 5 — mechanical fact extract (layer-stack planner)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: f9f8c120 (Grok executor). Parent: 954d9664.
Read-only. Do not edit files. Cite file:line. <500 words.

Do this:
```
git show --stat f9f8c120
git diff 954d9664..f9f8c120 --stat
```

Primary file: `astrid/packs/rendering/planners/layer_stack/run.py`
Tests: `tests/core/rendering/test_layer_stack.py`
Also: `planner.yaml`, `pack.yaml` +1, `astrid/packs/rendering/run.py`, `tests/core/rendering/test_freeze.py`

Print-only python / `git show` / grep ok. Do not run pytest or remotion.

## Do this

1. SCOPE. List every path in `954d9664..f9f8c120`. Flag ANY edit outside:
   - `astrid/packs/rendering/planners/layer_stack/**`
   - `astrid/packs/rendering/pack.yaml` (must be +1 planner id only)
   - `astrid/packs/rendering/run.py` (registration only?)
   - `tests/core/rendering/test_layer_stack.py`
   - `tests/core/rendering/test_freeze.py` (must add planner id only)
   Hybrids (`test_threejs_hybrid.py`, `test_legacy_hybrid.py`) must be untouched. Core/backend/finalizer/service must be untouched.

2. FAST PATH. Quote the exact loop that picks a full-stack winner.
   - Is it the FIRST eligible candidate whose real `support()` accepts the FULL timeline (not a heuristic like "if remotion in registry")?
   - What is passed as `request.profile` into that `support()`? Must be `None` (B5 oracle note: do not feed canonical h264 to stamped support).
   - What window is passed?
   - On success: one segment with `layer=None` + which finalizer id? Quote emission.

3. PER-TRACK CLAIM. Quote projection (`_component_timeline` or equivalent) + claim loop.
   - One visual track → one projection → first candidate whose `support()` accepts that projection?
   - `profile=None` here too?
   - What happens if no claimant? Does the error name the track? Is it a planner support rejection (structured reason) or an exception crash?

4. GREEDY MERGE. Quote merge predicate.
   - Adjacent same-renderer AND same-opacity only?
   - Is the winner re-asked `support()` on the MERGED projection before commit?
   - ffmpeg has a one-visual-track rule. Does re-support() reject two adjacent media tracks so they stay split? Cite the ffmpeg support check AND the merge re-support.

5. FAIL-CLOSED. For each of: `blendMode≠normal`, opacity outside `(0,1]`, no claimant — quote the check, the error type, and whether the offending track id is in the message.

6. PROFILE HONESTY.
   - Every `support()` call: quote `profile=` argument. Any call that passes canonical h264/yuv420p/mp4?
   - How does `_CommandSupportResolver` / support request materialize when `profile=None` + window? Quote the resolver if this planner constructs the request.
   - What is the emitted plan's `profile` (container/codec/pix_fmt)? Must stay canonical h264/yuv420p/mp4.

7. RECURSION. Does renderer selection forbid planner ids (including `rendering.layer-stack`)? Quote the filter.

8. TESTS. List each test name in `test_layer_stack.py` + one-line what it asserts. Note the forced-split test (threejs+ffmpeg only registry). Note whether remotion-capable → layer=None+concat and ffmpeg+text → two full-window + compositor are actually asserted.

## Report shape

```
SCOPE: clean|dirty — paths + hybrid/core/finalizer status
FAST: real-support|heuristic — profile= — window= — finalizer=
CLAIM: projection? first-support? profile= — no-claimant=
MERGE: predicate — re-support? ffmpeg-split-caught?
FAIL: blend / opacity / no-claimant → error-type + names-track?
PROFILE: all-support-None? plan-canonical?
RESOLVER: how profile=None materializes
RECURSION: planners-forbidden? Y/N + line
TESTS: name → assert
GAPS: any acceptance criterion not covered by a test
```
