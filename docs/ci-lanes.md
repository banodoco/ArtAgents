# CI Lanes

This document defines the official pytest lanes for the Astrid project. All lanes
are exercised via `scripts/reshape/run_ci_checks.sh`.

## Hard Gate: Default Lane

The default lane is a **hard gate with zero allowed failures**. Any test that
fails in this lane blocks the CI pipeline.

```bash
python3 -m pytest -q -m "not integration and not opt_in"
```

This lane runs every test that does **not** carry the `integration` or `opt_in`
marker. It is the canonical command exercised by the CI mirror in
`scripts/reshape/run_ci_checks.sh`.

Tests in this lane must:
- Run deterministically without external services, heavyweight fixtures, or
  environment-specific prerequisites.
- Complete quickly enough to serve as a pre-merge / pre-push check.

## Opt-In / Integration Lane

Tests that require external dependencies, heavyweight fixtures, or
environment-specific prerequisites are marked with both `integration` and
`opt_in`. They are excluded from the default lane and run only when explicitly
requested.

### Enumerated opt-in tests

| Test | Markers | Prerequisites |
|------|---------|---------------|
| `test_renderer_parity_against_sprint08_fixtures` | `renderer_parity`, `integration`, `opt_in` | `ASTRID_RENDERER_PARITY=1`, Node.js ESM runtime, committed sprint-08 fixtures |
| `test_e2e_local_smoke` | `integration`, `opt_in` | `vibecomfy` importable, `comfyui` binary on PATH |
| `test_hype_cut_invariants_on_discovered_run_dirs` | `standalone`, `hype_cut_invariants`, `integration`, `opt_in` | `HYPE_BRIEF_DIR` or `HYPE_DISCOVER_RUNS=1`, local `tools/runs` output with arrangement-mode brief directories |

### Running opt-in tests

```bash
# All integration/opt-in tests
python3 -m pytest -q -m "integration and opt_in"

# A specific opt-in test
python3 -m pytest -q -m opt_in tests/test_renderer_parity.py

# Everything (default + opt-in)
python3 -m pytest -q
```

### Prerequisite checks

Each opt-in test performs its own prerequisite validation at runtime (via
`pytest.skip` or `@pytest.mark.skipif`). These checks are **documented skips
only** — they fire inside opt-in execution when prerequisites are absent and do
not affect the default lane because the marker expression excludes the test from
collection entirely.

## Marker Reference

| Marker | Meaning |
|--------|---------|
| `integration` | Requires external dependencies, heavyweight fixtures, or env prerequisites |
| `opt_in` | Explicitly opt-in; never runs in the default lane |
| `slow` | Slower integration-style tests; opt-in for tight loops |
| `renderer_parity` | Optional renderer parity integration against sprint-08 fixtures |
| `standalone` | Test intended to run independently from the default suite |
| `hype_cut_invariants` | Standalone hype cut invariant coverage |

## Adding new opt-in tests

1. Add `@pytest.mark.integration` and `@pytest.mark.opt_in` to the test
   function.
2. If the test has existing specific markers (e.g., `renderer_parity`,
   `standalone`), preserve them alongside the new markers.
3. Add the prerequisite check as a `pytest.skip` or `@pytest.mark.skipif`
   inside the test — this is only exercised when the test is explicitly
   collected via an opt-in lane.
4. Update the enumerated table above.
