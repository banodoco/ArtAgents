# B5 authoritative validation evidence

Status: **BLOCKED**. The source-delta receipt and accepted clean-wheel delta receipt both report PASS before these runs (`.oracle/receipts/b5-source-rework-delta-luna.txt`, `.oracle/receipts/b5-clean-wheel-delta-luna.txt`). No product, test, or documentation files were changed.

## Frozen focused contract

Command, run once:

```bash
python3 -m pytest tests/packs tests/v10/test_catalog_migrations.py \
  tests/v10/test_m8_packaging.py tests/v10/test_pack_factoring.py \
  tests/v10/test_reference_repository.py tests/sdk/test_references.py \
  tests/sdk/test_extended_composition.py
```

Result: **exit 2**; `collected 1870 items / 1 error`; no tests executed, so pass/fail/skip/subtest counts are `0/0/0/0` plus one collection error. The unchanged rendering lane failed collection with `ModuleNotFoundError: No module named 'banodoco_timeline_schema'`. Pytest duration: `5.06s`; wall time: `6.06s`. Complete output: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/focused.txt`.

Adaptation: none. The required command was run with equivalent shell line continuations.

## Source doctor

Command, run once:

```bash
python3 -m astrid doctor
```

Result: **PASS**, exit 0, wall time `0.54s`; state `ready`; SQLite quick check and foreign-key integrity passed; migrations expected/applied `core/1, references/1, shots/1, timeline/1`, pending `0`; canonical census reports `22` product packs; documentation `22/22`; resources `551` handles. Complete output: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/doctor.txt`.

## Full authoritative suite

Command, run once:

```bash
python3 -m pytest
```

Result: **exit 2**; `collected 7631 items / 2 errors`; no tests executed, so pass/fail/skip/subtest counts are `0/0/0/0` plus two collection errors. Pytest duration: `19.90s`; wall time: `21.75s`. Complete captured output: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/full.txt`.

The first error is the previously reproduced rendering lane and has the unchanged missing-dependency signature `ModuleNotFoundError: No module named 'banodoco_timeline_schema'`. Per the B5 rule, the additional `tests/timeline/test_inverses.py` collection error is not waived as the previously reproduced rendering lane. Smallest focused reproducer, run once: `python3 -m pytest tests/timeline/test_inverses.py`, exit 2, `collected 0 items / 1 error`, wall time `0.90s`; it raises the same unavailable dependency through `TimelineEventSchemaError`. Complete output: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/b5-validation/timeline-inverses.txt`.

## Disposition

Baseline-only: the previously reproduced rendering failure remains unchanged and is not suppressed, vendored, or faked. New finite B5 blocker: `tests/timeline/test_inverses.py` collection failure under the unavailable `banodoco_timeline_schema` dependency; it was not the previously reproduced rendering-lane failure. No second full suite was run.
