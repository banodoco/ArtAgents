# Orchestrator Run Persists

You are running a structural M4 verification scenario.  No live agent
dispatch is performed — the fixture primes the project deterministically
and the check verifies frozen evidence.

## What happens

1. A project is created with slug `${SLUG}`.
2. The fixture runs `video_editing.event_talks --project ${SLUG} --dry-run`
   to prove terminal orchestrator execution succeeds.
3. The fixture verifies that `events.jsonl` contains at least one
   `produces` event and that produced artifacts match their expected
   CAS hashes.
4. Diagnostic evidence is written to `m4/orchestrator_run_persists.json`.
5. The capture phase freezes the evidence pack for deterministic M4 checks.

## Canonical CLI constraint

- **Do NOT invoke `python -m astrid.packs.*` directly.** The only
  canonical CLI surfaces are `astrid executors run <id> ...` and
  `astrid orchestrators run <id> ...`. Bypassing them disqualifies the
  run regardless of artifacts produced.

## Evidence left behind

| Path | Description |
|---|---|
| `m4/orchestrator_run_persists.json` | Diagnostic payload: `terminal_status`, `run_json_status`, `artifacts_match_cas`, `produces_event_count`, `artifact_count` |
| `runs/*/events.jsonl` | Event log containing at least one produces event |
| `runs/*/run.json` | Run metadata confirming terminal success |
| `m4/lease.json` | Frozen lease file (captured if present) |

## Deterministic assertion

**`m4.orchestrator_run_persists.terminal_success`** — verifies:
- `terminal_status == "success"`
- `run_json_status == "success"`
- `artifacts_match_cas == true`
- `produces_event_count >= 1`
- `artifact_count >= 1`

## M2 universal checks

This scenario sets `assessment.universal_checks: false`. No M2 checks
(C3, C4, S1, S2) are enabled. All verification is performed by the
deterministic M4 check above.

## Report (under 200 words, markdown, numbered sections)

Each numbered section MUST have at least 2 substantive sentences.

1. **Orchestrator terminal execution** — did the dry-run succeed?
   What exit code and output did `event_talks --dry-run` produce?
2. **Event log contents** — what produces events appeared in
   `events.jsonl`? How many? What artifact hashes were recorded?
3. **Artifact CAS verification** — did all produced artifacts match
   their expected CAS hashes? List any mismatches.
4. **Evidence completeness** — are all expected evidence files
   present? Is `m4/orchestrator_run_persists.json` well-formed?

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a fixture, not an agent task.
- Verify behaviour from frozen evidence files, not from narrative output.
