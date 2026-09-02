# B5 timeline collection baseline

## Base export

- Custody base commit: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- Custody base tree: `2c348e96c860f76ba0ce1d5b83d72a423f0d6f8e`
- Export archive SHA-256: `c5286bc2d79d12f8d4ad33f30801dd89c5f820dabacabc5392e252814dd86b53`
- Export: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/timeline-base-export`
- Archive command: `git archive --format=tar --prefix=timeline-base-export/ 7ac50c12e8e4d90988fee603ffdb9896e5628792`
- Identity/overlay proof: the export was created directly from the immutable commit with `git archive`; no checkout files, working-tree changes, or current-tree overlay were copied. The required test file exists in the export.

## Focused base command

Command, run from the isolated export with the inherited Python/dependency environment:

```text
python3 -m pytest tests/timeline/test_inverses.py
```

Result: exit status `2`; `collected 0 items / 1 error`; collection interrupted after `1 error in 0.18s`. Complete captured output: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/timeline-inverses-baseline.txt`.

Environment reported by pytest: Python `3.11.11`, pytest `9.0.2`, pluggy `1.6.0`, cov `7.1.0`, timeout `2.4.0`, anyio `4.14.2`.

## Comparison

Current focused evidence (`/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/timeline-inverses.txt`) records the same command and result: exit `2`, zero collected items, one collection error. Both traces have the same relevant import path:

`tests/timeline/test_inverses.py:259` -> `TimelineConfigReplacedPayload` -> `config.py:103` -> `TimelineEventSchemaError`, caused by `banodoco_schema.py:_shared_load_schema` raising `ImportError` because `banodoco_timeline_schema` is unavailable.

The missing module and message are identical: `banodoco_timeline_schema is required for timeline validation — pip install -e packages/timeline-schema/python`. The base and current timeline signatures are therefore the same. The only focused-output differences are the expected `rootdir` and elapsed time. Current full evidence (`/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/full.txt`) contains this same `tests/timeline/test_inverses.py` error; its separate rendering-parity `ModuleNotFoundError` is outside this focused timeline comparison.

## Scope

Only this evidence file was changed. No product, test, or documentation file was edited; no broad suite was run.
