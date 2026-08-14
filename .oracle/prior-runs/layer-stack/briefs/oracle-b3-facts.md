# Oracle Batch 3 — mechanical fact extract

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: edf0859a (Flash). Parent: cf947761.
Read-only. Do not edit files. Cite file:line from the working tree. <450 words.

## Do this

1. `git show edf0859a --stat` then `git diff cf947761..edf0859a --stat`. Flag ANY path outside:
   `astrid/packs/rendering/finalizers/compositor/**`,
   `astrid/packs/rendering/pack.yaml`,
   `tests/packs/rendering/test_ffmpeg_compositor.py`,
   `tests/core/rendering/test_freeze.py`.
   Confirm concat finalizer (`finalizers/ffmpeg/`) is byte-identical to parent.

2. `git diff cf947761..edf0859a -- tests/core/rendering/test_freeze.py`. Quote the entire freeze hunk. Confirm the ONLY change is adding `rendering.ffmpeg-compositor` to a finalizer id set. Flag any other freeze assertion change.

3. Read `astrid/packs/rendering/finalizers/compositor/run.py`. Quote (with line numbers):
   - `support()` rejection cases: layer=None, single-z, blend!=normal, <2 distinct z, missing profile. Exact reason strings.
   - `build_composite_command` (or equivalent): where `-c:v libvpx-vp9` is inserted relative to each `-i`. Is it BEFORE every alpha input? Every input? Conditional?
   - overlay filter: exact `eof_action=` value, `format=`, `alpha=` if any.
   - per-layer chain: `format=yuva420p`? `scale`? `pad`? `setsar`? `fps`? `setpts`? When is `colorchannelmixer` added (always vs opacity<1)?
   - How output length is pinned: `-t`? `tpad`? `color=...:d=`? `plan.total_frames` vs sum of segment durations? Quote the duration source.
   - Audio: how lowest-z-with-audio is chosen; `anullsrc` path; `-map` order.

4. `finalizer.yaml` + `pack.yaml` registration: quote id and the pack.yaml list entry. Confirm operations include finalize+support.

5. Tests: list every test name in `tests/packs/rendering/test_ffmpeg_compositor.py`. For each: what it asserts (not paraphrased). Flag:
   - tautologies
   - missing: short BOTTOM layer; BOTH layers short; opacity<1 pixel proof; NTSC fps (30000/1001) pixel/frame proof; premultiplied; mixed windows if support claims to reject them
   - whether pixel proofs decode real frames (PIL/ffmpeg extract) vs only check command strings

6. Count lines of `run.py` and the existing `finalizers/ffmpeg/run.py`. Note duplicated helpers.

7. Do not run pytest (host will). Print-only python is ok.

## Report shape

```
PATHS: ...
SCOPE: clean|dirty — ...
FREEZE: only-id|other — ...
SUPPORT: list reject cases + reason strings
VP9: before-alpha-inputs|always|missing — lines
OVERLAY: eof_action=?, format=?, alpha=?
CHAIN: filters present? colorchannelmixer gated?
DURATION: source of seconds/frames; guaranteed = plan.total_frames?
AUDIO: lowest-z selection + silent path
YAML: registered?
TESTS: one line per test
HOLES: untested vs brief/checkpoint
SIZE: compositor run.py N vs ffmpeg run.py M
```
