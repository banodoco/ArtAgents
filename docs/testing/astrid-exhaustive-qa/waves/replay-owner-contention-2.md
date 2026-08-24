# Replay: owner contention 2

Date: 2026-08-23  
Mode: live CLI/HTTP agent UX (no programmatic tests)  
Isolated projects root: `/tmp/astrid-owner-contention-2.L19H7q`  
Bridge port: `18743`

## Scenario

Created a fresh `handoff-demo` project and default `primary` timeline (version
1), then started editor A with `astrid serve`. While A owned the store, editor
B exercised discovery and reads over HTTP, and attempted the same operations
through the product CLI.

## Evidence

- `GET /routes` returned the machine-readable bridge routes and explicitly
  explained exclusive ownership, HTTP usage during the session, and shutdown
  handoff semantics.
- `GET /projects`, `GET /projects/handoff-demo/timelines`, and
  `GET /projects/handoff-demo/timelines/primary` all returned successful,
  useful reads while the bridge was live.
- CLI `projects show handoff-demo --json` returned exactly the five-key
  envelope (`ok`, `data`, `error`, `receipt`, `idempotency_key`) with
  `error.code=unavailable`, `details.reason=store_owned`,
  `details.retryable=true`, and actionable HTTP-or-clean-shutdown guidance.
- CLI timeline write with the exact payload and explicit key
  `owner-contention-2-save` returned the same typed unavailable envelope while
  A was live; no mutation occurred.
- After cleanly stopping A, retrying that exact payload/key succeeded at
  version 2. Replaying it again returned the same version-2 data and identical
  receipt/event/request hash, demonstrating idempotency without a second
  mutation.
- A fresh-key write with stale `--expected-version 1` returned typed
  `stale_version` with `current_version=2`, `expected_version=1`, and explicit
  no-write/merge recovery guidance.
- Final `timelines history --json` contained exactly two versions: created
  version 1 and one saved version 2 containing asset `b`; the stale `c` write
  was absent.
- No response was an unstructured bug/error.

## Verdict

**PASS.** The owner-contention UX is stable and retryable, preserves the exact
write payload/idempotency key across handoff, safely replays idempotently, and
keeps stale writes typed and mutation-free. Final history is exactly two
versions.
