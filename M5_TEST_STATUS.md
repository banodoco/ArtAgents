# M5 Test Status

Milestone 5 (Integration, Docs, and Agent Proof) — test status as of the final
post-review validation sweep.

## Test Suite Results

| Suite | Passed | Failed | Notes |
|-------|--------|--------|-------|
| Core pack tests (9 files) | 134 | 0 | Includes fork-aware gateway help assertions |
| Agent discovery scenario | 1 | 0 | New test, passes in ~0.4s |
| Sprint1 regression | 31 | 0 | Existing regression guard |
| **Total** | **175** | **0** | 272 subtests also passed |

## Failing Tests

None in the final post-review validation sweep. The previously stale
`test_root_help_explains_canonical_gateway` assertions were updated to include
the `fork` subcommand for orchestrators and executors.

## Pre-Existing Debt

### DEBT-001, DEBT-002, DEBT-003 (Sprint 1 Regression)

- **File:** `tests/test_sprint1_regression.py` (397 lines)
- **Issue:** Line 7 references a non-existent file `test_canonical_aliases.py`.
  This file was planned in M1 but never created. The only related test file is
  `tests/test_canonical_cli.py` (257 lines). The sprint1 regression test itself
  passes (31/31) because it uses `assertGreaterEqual` floors that remain valid.
- **Impact:** Documentation/cosmetic — the docstring references a ghost file.
  No test behavior is affected.
- **Blocker:** None.

## Validation Results

### packs status --json

All 6 packs discovered and listed. Validation errors are zero:

| Pack | Errors | Warnings | Notes |
|------|--------|----------|--------------|
| builtin | 0 | 2 | recommended `AGENTS.md` / `README.md` not found |
| external | 0 | 2 | recommended `AGENTS.md` / `README.md` not found |
| iteration | 0 | 2 | `AGENTS.md: recommended file not found`, `README.md: recommended file not found` |
| local | 0 | 2 | recommended `AGENTS.md` / `README.md` not found |
| seinfeld | 0 | 2 | recommended `AGENTS.md` / `README.md` not found |
| upload | 0 | 2 | recommended `AGENTS.md` / `README.md` not found |

**Blocker:** None. The remaining findings are warnings for recommended
pack-root docs, not validation errors.

**Zero validation errors.** Older shipped pack and element manifests now declare
`schema_version: 1`, and element ids are validated by kind-qualified identity.

### skills doctor --json

- **Detected harnesses:** claude, codex, hermes
- **Results:** All 6 checks (3 harnesses × 2 skill packs) report `"ok": false,
  "message": "not installed"`
- **Informational only:** Non-zero findings are expected in headless/CI
  environments without agent harnesses installed (`claude`, `codex`, `hermes`
  CLIs are not present). This is not a regression or failure.
- **Lint:** None
- **Drift:** None
- **Healed:** None

### packs list --json

All 6 expected packs are present and visible:

1. **builtin** — Astrid Built-in (version 1.0.0)
2. **external** — Astrid External Tools (version 1.0.0)
3. **iteration** — Astrid Iteration (version 1.0.0)
4. **local** — Local Scratch Pack (version 0.1.0)
5. **seinfeld** — Seinfeld Scene Generator (version 0.1.0)
6. **upload** — Astrid Upload (version 1.0.0)

Output is valid JSON with no errors.

## Summary

- **175 tests pass, with 272 subtests passed.** No failures remain in the final
  focused pack-system validation sweep.
- **Zero validation errors.** `packs status --json` reports no errors across
  all six discovered packs.
- **Skills doctor findings are informational.** No agent harnesses are installed
  in this environment.
- **All 6 packs are discoverable and listed correctly.**
- **Agent discovery scenario test (`test_agent_discovery_scenario.py`) passes**
  in under 1 second and never reads source files directly.
