# Timeline Concurrent Version Conflict

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture creates a timeline and performs two sequential appends
   at the same `expected_version`, simulating a version/CAS race.
3. The first append (winner) succeeds. The second append (loser) is
   rejected with a deterministic `EventLogStaleVersionError`.
4. The winner's append is verified, chain integrity is confirmed, and
   the conflict mechanism is proven version/CAS-based without lease
   coupling.
5. Diagnostic evidence is written to
   `m4/timeline_concurrent_version_conflict.json`.
6. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/timeline_concurrent_version_conflict.json` | Diagnostic payload: `loser_error`, `winner_appended`, `verify_chain_ok`, `mechanism`, `mentions_lease` |
| `timelines/*/assembly.jsonl` | Event log with winner's append only (loser rejected) |

## Deterministic assertion

**`m4.timeline_concurrent_version_conflict.stale_version_conflict`** — verifies:
- `loser_error == "EventLogStaleVersionError"`
- `winner_appended == true`
- `verify_chain_ok == true`
- `mechanism` is `"expected_version_conflict"` or `"cas_conflict"`
- `mentions_lease == false` (conflict is version/CAS-based, not lease-based)

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Race simulation** — how were the two conflicting appends
   constructed? What `expected_version` was used?
2. **Winner behaviour** — did the first append succeed? What event
   was written to the event log?
3. **Loser rejection** — was the second append rejected with
   `EventLogStaleVersionError`? What error message was produced?
4. **Conflict mechanism** — is the conflict mechanism
   `expected_version_conflict` or `cas_conflict`? Does the
   diagnostic mention leases at all?
5. **Evidence completeness** — are all expected evidence files
   present? Is `m4/timeline_concurrent_version_conflict.json`
   well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
