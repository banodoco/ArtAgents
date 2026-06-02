# Durability After Crash

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture writes a deliberate head-vs-jsonl desync under
   `m4/desync/` — `assembly.head.json` and `assembly.jsonl` are
   deliberately mismatched outside normal timelines, simulating
   corruption after a crash.
3. The detection mechanism flags the mismatch kind as
   `head_vs_jsonl_desync` without serving stale state.
4. The desync artifacts (`assembly.head.json`, `assembly.jsonl`)
   are preserved alongside the diagnostic for deterministic
   verification.
5. Diagnostic evidence is written to
   `m4/durability_after_crash.json`.
6. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/durability_after_crash.json` | Diagnostic payload: `detection_ok`, `mismatch_kind`, `served_stale_state` |
| `m4/desync/assembly.head.json` | Deliberately mismatched head snapshot |
| `m4/desync/assembly.jsonl` | Deliberately mismatched event log |

## Deterministic assertion

**`m4.durability_after_crash.head_jsonl_desync_detected`** — verifies:
- `detection_ok == true` (the desync was detected)
- `mismatch_kind == "head_vs_jsonl_desync"` (correct mismatch type)
- `served_stale_state == false` (no stale state was served)

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Desync construction** — how were `assembly.head.json` and
   `assembly.jsonl` deliberately mismatched? What field(s) differ?
2. **Detection behaviour** — did the detection mechanism flag the
   mismatch? Was `mismatch_kind` correctly identified as
   `head_vs_jsonl_desync`?
3. **Stale state guard** — did the system serve any stale state
   before detecting the desync? Is `served_stale_state` false?
4. **Evidence completeness** — are all expected evidence files
   present? Are the desync artifacts well-formed and verifiable?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
