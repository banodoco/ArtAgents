I'll re-review the three r5 fixes against the incremental diff and the claimed tests, then give a binary verdict.HEAD matches `C8-batch7-done`. Next I’ll read the r5 verdict and the three claimed fixes in the incremental diff.r5 named three holes. I’ll read the current handlers and registry conflict API, then run the claimed tests.The conflict API may not match inspect. I’ll read how the registry records conflicts and whether any test actually inspects a conflicting id.The contract tests only check that the `conflicts` key exists. I’ll run the claimed suites and live-probe real conflicts plus support exit codes.The allowlist and contract tests passed; three other gate tests failed on a missing timeline-schema install. I’ll rerun with the project environment and live-probe conflicts plus support exits.Pytest is still running. I’ll live-probe inspect conflicts and support exit codes in parallel.549 tests passed. Next I’ll live-probe real inspect conflicts, declining-support exits, and the unbound CLI.The three r5 holes are closed in code and in live CLI, not just in tests.

**PASS**

HEAD is `2107af83` / `C8-batch7-done`. The three r5 items hold.

### 1. Sprint 1 allowlist lock
`EXPECTED_SPRINT1_UNBOUND_ALLOWLIST` now matches `SPRINT1_UNBOUND_ALLOWLIST_CONTRACT`, including `("renderers",)` and `("replay",)`.

`test_unbound_gate_uses_the_frozen_allowlist_table` **PASSED**. Live, unbound: `renderers list` / `inspect rendering.ffmpeg` exit 0 with no session gate; `replay` is argparse usage (exit 2), not `no session bound`; `timelines ls` is still gated.

### 2. Inspect reports real conflicts
`_resolve_inspect_evidence` fills `conflicts` from `registry.candidates(id)` when more than one static candidate exists. Live two-root `sharedrender.renderer`:

- JSON: two entries with `source_kind` / `pack_id` / `priority_index` / `manifest_digest`
- Plain: `conflicts: sharedrender.renderer (extra, priority 20), sharedrender.renderer (extra, priority 21)` plus `overrides:`

Built-in `rendering.ffmpeg` still emits `conflicts: []`. Using `candidates()` rather than `conflicts()` is the right static inspect surface: ineligible duplicates are visible instead of hidden.

### 3. Support expected errors exit 2
Unknown and declining backends, JSON and plain, all exit **2**. Only `kind == "internal"` returns 1. Plain mode prints `error:` and `recovery:`.

### Suites
- `test_cli_contract.py` — 31 passed
- `tests/core/rendering` + `tests/session/test_cli_gate.py` — **549 passed**
- `scripts/reshape/check_repo_hygiene.py` — exit 0

Phase 6 can proceed.
