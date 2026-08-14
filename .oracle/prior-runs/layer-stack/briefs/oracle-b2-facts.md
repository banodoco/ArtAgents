# Oracle Batch 2 — mechanical fact extract

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: dce60b9f (Flash). Parent: 5f7b1803.
Read-only. Do not edit files. Cite file:line. <400 words.

## Do this

1. `git show dce60b9f --stat` then `git show dce60b9f -- astrid/core/rendering/service.py`. Quote both hunks with line numbers from the working tree (not just the patch). Confirm exactly two service.py change sites.

2. `_window_timeline` (`astrid/core/rendering/service.py`):
   - Signature (keyword-only `tracks`?).
   - When `tracks is None`: is the used-tracks prune identical to parent 5f7b1803? Diff the function against parent: `git show 5f7b1803:astrid/core/rendering/service.py` vs HEAD. Flag ANY byte change on the None path (including whitespace, comments, call-order of `_window_clip`).
   - When `tracks` is provided: are clips pre-filtered BEFORE `_window_clip` rewriting? Quote the filter order.
   - Track-list filter: original tracks intersect allowlist, or allowlist as-is? Can an allowlist id that is NOT in the original timeline's `tracks` appear in the output track list?
   - Empty-window allowlisted track: does a track in the allowlist survive with zero in-window clips? Quote how.

3. `_segment_request`:
   - How is `tracks=` passed? Quote the ternary.
   - Metadata stamp: exact key, exact dict, `setdefault` vs assignment, does it clobber existing `metadata` keys or existing `astrid_layer`? Quote the merge.
   - Is the stamp gated on `segment.layer is not None` only (includes z=0)?
   - Confirm `layer is None` path: `_window_timeline` called without `tracks=` / with None, and no metadata write.

4. Scope: `git diff 5f7b1803..dce60b9f --stat`. Flag any path outside `service.py` + `tests/core/rendering/test_service.py`. Grep the commit for pack/finalizer/planner/dispatch/output_name/provenance edits.

5. Tests: list every NEW test name in `tests/core/rendering/test_service.py` (git diff against parent). For each: exact assertion (not paraphrased). Flag tautologies. Confirm the 6 claimed cases exist: v2-only slice; layer=None prune unchanged; allowlisted track survives empty window; z1 alpha True merged; z0 alpha False; end-to-end via capture transport.

6. Grep `astrid_layer` across the repo. List every consumer. Note if Batch 4 renderers already read it.

7. If needed, a print-only python snippet. Do not change tests. Do not run pytest (host will).

## Report shape

```
PATHS: ...
SCOPE: clean|dirty — ...
WINDOW_SIG: ...
NONE_PATH: identical|changed — ...
ALLOWLIST: clip-filter-before-rewrite? yes|no — ...
PHANTOM_TRACK: added|filtered — (allowlist id absent from original timeline)
EMPTY_SURVIVES: yes|no — ...
STAMP: key, shape, merge behavior, z=0 included?
LAYER_NONE_REQUEST: unchanged|changed — ...
TESTS: one line per new test
CONSUMERS: ...
HOLES: untested or mismatched vs brief
```
