# Timeline Large Audit

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture creates a timeline and appends at least 500 valid
   timeline events via the production CRUD/edit APIs, cycling
   through edit types to build a large-scale chain.
3. After every batch, chain integrity is verified. After all 500+
   events, `verify_chain_ok` and `within_budget` are confirmed.
4. Diagnostic evidence is written to
   `m4/timeline_large_audit.json`.
5. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/timeline_large_audit.json` | Diagnostic payload: `event_count`, `verify_chain_ok`, `within_budget` |
| `timelines/*/assembly.jsonl` | Event log with 500+ valid timeline events |

## Deterministic assertion

**`m4.timeline_large_audit.large_chain_verified`** — verifies:
- `event_count >= 500` (at least 500 events were appended)
- `verify_chain_ok == true` (the full chain passes verification)
- `within_budget == true` (the operation stayed within resource budget)

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Event generation** — how many events were appended? What edit
   types were cycled through to reach 500+?
2. **Chain integrity at scale** — did `verify_chain` pass after
   every batch? Did it pass on the final 500+ event chain?
3. **Budget adherence** — did the operation stay within budget?
   What was the wall-clock time and token consumption?
4. **Evidence completeness** — are all expected evidence files
   present? Is `m4/timeline_large_audit.json` well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
