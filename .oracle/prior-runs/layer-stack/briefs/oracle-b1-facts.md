# Oracle Batch 1 — mechanical fact extract

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commits: d5b960d7 (Flash) + fe7622c7 (host fix).
Read-only. Do not edit files. Cite file:line. <350 words.

## Do this

1. `git show --stat d5b960d7` and `git show --stat fe7622c7`. List every path touched.
2. Read LayerRef + RenderSegment.layer + RenderPlan.__post_init__ cursor in `astrid/core/rendering/contracts.py`. Quote:
   - LayerRef fields and validation (z, tracks, blend, opacity)
   - RenderSegment.layer default; `to_dict` omit-when-None
   - cursor type; all-or-none rule; first-segment / same-z overlap-gap; trailing-gap condition (which keys must reach target_end)
3. Read `astrid/core/rendering/schemas/v1/plan.json` `renderSegment.layer` (required, additionalProperties).
4. Confirm no service/pack/finalizer edits in those two commits (`git diff 4c00b2a0..fe7622c7 --stat` — flag any path outside contracts.py, plan.json, tests).
5. Read `tests/core/rendering/test_layer_contract.py`. List each test name + the exact assertion (not paraphrased). Flag tautologies (assert X == X, only checking "does not raise" with no property).
6. Grep `test_contracts.py` for the frozen fast-path key-set (~600-603) and overlap/gap matrix (~1084-1100). Confirm they still exist and still ignore `layer`.
7. Probe with a tiny python snippet IF needed (print-only). Do not change tests.

## Report shape

```
PATHS: ...
LAYERREF: ...
TO_DICT: ...
CURSOR: ...
TRAILING: ...
SCHEMA: ...
SCOPE: clean|dirty — ...
TESTS: one line per test
FROZEN: still holds | broken — ...
HOLES: missing validations or untested rules
```
