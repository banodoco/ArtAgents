# Timeline Compose Edit

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture creates a timeline and appends one edit event per
   feature axis via the production CRUD/edit APIs:
   `track`, `clip`, `audio_bind`, `transition`, `effect`, `theme`.
3. Chain integrity, head consistency, and projection fidelity are
   verified after every append.
4. The fixture confirms all six feature axes are present in the
   final projection.
5. Diagnostic evidence is written to `m4/timeline_compose_edit.json`.
6. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/timeline_compose_edit.json` | Diagnostic payload: `verify_chain_ok`, `head_consistency_ok`, `projection_fidelity_ok`, `features_present` |
| `timelines/*/assembly.jsonl` | Event log with all six feature-axis edit events |
| `timelines/*/assembly.json` | Head snapshot for consistency verification |

## Deterministic assertion

**`m4.timeline_compose_edit.composite_projection`** — verifies:
- `verify_chain_ok == true`
- `head_consistency_ok == true`
- `projection_fidelity_ok == true`
- `features_present` contains all six axes: `track`, `clip`,
  `audio_bind`, `transition`, `effect`, `theme`

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Timeline creation and edit sequence** — what timeline was created?
   List each edit event appended, in order, with its feature axis.
2. **Chain integrity** — did `verify_chain` pass after every append?
   Were any hash mismatches detected during the sequence?
3. **Projection fidelity** — does the final projection contain all six
   feature axes? Are any axes missing from `features_present`?
4. **Evidence completeness** — are all expected evidence files
   present? Is `m4/timeline_compose_edit.json` well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
