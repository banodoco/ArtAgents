# Task Run Concurrent Lease

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture creates a `lease.json` for one writer, establishing
   single-writer ownership with a specific epoch.
3. A conflicting write is attempted with a different epoch. This is
   rejected with a deterministic `StaleEpochError` or
   `NotWriterError`, proving lease enforcement for concurrent
   task-run access.
4. The winner's `events.jsonl` remains valid and the frozen
   `lease.json` is captured as evidence.
5. Diagnostic evidence is written to
   `m4/taskrun_concurrent_lease.json`.
6. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/taskrun_concurrent_lease.json` | Diagnostic payload: `rejection_error`, `writer_count`, `verify_chain_ok`, `lease_file_present` |
| `runs/*/events.jsonl` | Valid event log from the winning writer |
| `runs/*/lease.json` | Frozen lease file proving single-writer ownership |

## Deterministic assertion

**`m4.taskrun_concurrent_lease.single_writer_lease`** — verifies:
- `rejection_error` is `"StaleEpochError"` or `"NotWriterError"`
- `writer_count == 1` (single writer holds the lease)
- `verify_chain_ok == true` (winner's log is valid)
- `lease_file_present == true` (lease file is captured)

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Lease creation** — how was `lease.json` created? What epoch and
   writer identity were recorded?
2. **Conflicting write attempt** — what epoch was used for the
   conflicting write? How did it differ from the holder's epoch?
3. **Rejection behaviour** — was the conflicting write rejected with
   `StaleEpochError` or `NotWriterError`? What error message was
   produced?
4. **Winner's log integrity** — does the winner's `events.jsonl`
   pass `verify_chain`? Is the lease file present and well-formed?
5. **Evidence completeness** — are all expected evidence files
   present? Is `m4/taskrun_concurrent_lease.json` well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
