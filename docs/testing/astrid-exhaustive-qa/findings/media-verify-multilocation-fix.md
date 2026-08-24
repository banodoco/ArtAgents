# Multi-location media verification fix

Date: 2026-08-23 (Europe/Berlin)

## Live failure

The independent portable-backup replay restored one content-deduped media row
with two `external_local` locations. `doctor` verified both locations, but the
public command below returned a generic `conflict` error:

```text
astrid media verify <media-id> --project replay-external-2 \
  --realm external_local
```

The same command worked for single-location media, so the dedupe shape was the
only failed gate.

## Root fix

`media verify` now verifies every matching location in deterministic
`created_at, id` order by default. The SDK and CLI accept mutually exclusive
`location_id`/`--location-id` and `locator`/`--locator` selectors for precise
retries. The repository verification request identity includes the selected
location, preventing cross-location idempotency replay.

Single-location calls retain the historical full media read model and receipt
shape. Multi-location success returns an aggregate with bounded per-location
results, counts, and the refreshed media model. A mixed result is a typed
`integrity_error`, not a generic conflict; its details include every location,
successful and failed counts, recovery selectors, and the mutation policy. The
per-location list is bounded to 32 records and reports total/truncated counts.

Mutation policy is intentionally partial-success: each healthy location's
`verified_at` and verification event commits independently; a missing or
mutated location remains unchanged. This makes one bad path unable to hide
healthy paths while keeping each individual location update atomic.

## Verification

Fresh live portable-restore replay:

- two identical external paths restored to one media id with two locations;
- default `media verify --realm external_local` returned `ok: true`,
  `verified_count: 2`, and two deterministic per-location successes;
- deleting one restored digest path left the alias location healthy;
- repeating the default command returned typed `integrity_error` with
  `verified_count: 1`, `failed_count: 1`, both location records, and explicit
  partial-success guidance;
- retrying the surviving location with `--locator <path>` returned the normal
  successful media result and receipt.

Targeted tests: `75 passed` from
`tests/sdk/test_media.py` and `tests/v10/test_domain_cli_media_references.py`,
including new duplicate-location success, mixed-health aggregate, and precise
selector coverage.
