# CI Lanes

This document describes the CI lane system exercised by `scripts/reshape/run_ci_checks.sh`.

## Script Sandbox

Every invocation of `run_ci_checks.sh` is **hermetic by construction**. The script creates
fresh temporary directories for `ASTRID_HOME` and `ASTRID_PROJECTS_ROOT` via `mktemp -d`
before any lane runs (line 9–12 of the script):

```bash
ASTRID_HOME="$(mktemp -d)"
export ASTRID_HOME
ASTRID_PROJECTS_ROOT="$(mktemp -d)"
export ASTRID_PROJECTS_ROOT
```

Both variables are `export`ed so subprocesses (pytest, ruff, mypy, npm typecheck, etc.)
inherit them automatically.

**Ordering matters.** `ASTRID_HOME` is exported *first*, then a minimal CI agent identity
is seeded so first-run bootstrap never fires:

```bash
"$PYTHON_BIN" -c 'from astrid.core.session.identity import Identity, write_identity; write_identity(Identity(agent_id="ci", created_at="2026-01-01T00:00:00Z"))'
```

An `EXIT` trap ensures both temporary directories are cleaned up when the script exits,
whether by success, failure, or signal:

```bash
trap 'rm -rf "$ASTRID_HOME" "$ASTRID_PROJECTS_ROOT"' EXIT
```

This means concurrent CI invocations never touch the developer's real `~/.astrid` or
`DEFAULT_PROJECTS_ROOT`. Each invocation is fully isolated.

When `--json` mode is active, the trap is extended to also clean up the JSON temporary
directory (used for junit XML files).

## Lane Overview

The script exercises seven stable lanes, plus an optional `--changed` fast path:

| Lane | What it exercises | Type |
|------|-------------------|------|
| `baselines` | ruff, mypy, repo hygiene | Plain (exit-code) |
| `docs` | `tests/verify_docs_commands.sh` | Plain (exit-code) |
| `reshape` | `tests/reshape/` + hype regression fixture + concurrency smoke | pytest |
| `blocking` | Targeted tests, all `tests/core/rendering`, and the pinned Remotion renderer-parity gate | pytest |
| `broad` | Full suite: `-m "not integration and not opt_in"` | pytest |
| `remotion_typecheck` | Pinned Node/npm, lockfile `npm ci` when needed, generated types, then `npm run typecheck` | Plain (exit-code) |
| `quarantine` | `QUARANTINE_TESTS` (opt-in, non-blocking) | pytest (per-file) |

## `--json` Mode

Pass `--json` to emit a single JSON object on **stdout** and nothing else. All human
progress text, lane banners, and subprocess output are routed to **stderr**.

### JSON Schema

```jsonc
{
  "lanes": {
    "baselines":           { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "docs":                { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "reshape":             { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "blocking":            { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "broad":               { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "remotion_typecheck":  { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" },
    "quarantine":          { "passed": int, "failed": int, "skipped": int, "status": "pass|fail|skip" }
  },
  "ok": true|false,
  "exit": int
}
```

- **Lane keys** are the stable set listed above. The `--changed` fast path (see below) uses
  a `"changed"` key instead.
- **`ok`** is `true` iff `exit` is `0` (i.e. every lane passed).
- **`exit`** matches the process return code.
- **Counts** for pytest lanes (`reshape`, `blocking`, `broad`) are derived from
  `--junit-xml` output parsed with Python's `xml.etree.ElementTree`:
  `passed = tests - failures - errors - skipped`. Plain lanes use exit code: `0` → 1 pass;
  non-zero → 1 fail.
- **stdout-leaking lanes** (`run_quarantine_lane` and the remotion typecheck) have their
  stdout captured and rerouted to stderr by the `--json` wrapper — the lane functions
  themselves are **not** modified (SD-003).

### Fast subset via environment variable

Set `ASTRID_CI_SKIP_BROAD=1` to skip the `broad` lane (reported as `skipped: 1`). This is
useful for fast CI self-tests that only need to verify JSON shape, not the full suite.

## `--changed` Fast Lane

Pass `--changed` to replace the **entire** script execution with a fast, targeted test
selection. All baseline, docs, reshape, blocking, remotion, and quarantine lanes are
**skipped** — only tests mapped from changed source files are run. This is the only way to
achieve sub-90-second CI feedback.

### Merge-base computation (3-tier fallback)

The script determines which files changed using a 3-tier merge-base fallback chain:

1. `git merge-base HEAD origin/main` — primary target.
2. `git merge-base HEAD main` — fallback when `origin/main` is unavailable.
3. `HEAD~1..HEAD` — last resort when neither merge-base exists (e.g. shallow clones,
   detached HEAD).

The diff is computed with `git diff --name-only $BASE...HEAD` for tiers 1–2 and
`git diff --name-only HEAD~1..HEAD` for tier 3.

### Name-based selection heuristic

Changed files are mapped to test paths via three ordered rules:

| Rule | Trigger | Action |
|------|---------|--------|
| **1** | Path starts with `tests/` | Select directly (the file itself is the test). |
| **2** | `astrid/<mod>.py` (top-level module, no subdirectory) | Select `tests/test_<mod>.py` if it exists. Never falls back to whole `tests/`. |
| **3** | `astrid/<sub>/.../<mod>.py` (nested module) | (a) Try `tests/test_<mod>.py` directly. (b) Walk the full mirrored directory path, e.g. `astrid/core/session/foo.py` → `tests/core/session/`. (c) Drop leading path components one at a time, selecting the first existing directory. For example, `astrid/core/session/foo.py` drops `core/` to try `tests/session/` — this catches the common pattern where `astrid/core/session/` maps to `tests/session/`. |

After all mappings, selections are **de-duplicated** (`sort -u`). If the final selection is
empty (no changed source files mapped to any test), the script falls back to
`TARGETED_BLOCKING_TESTS`.

Selected tests run with `-q` (quiet) and **without** `--cov`.

### Caveats (best-effort)

- The heuristic is pattern-based, not import-graph-based. A changed module whose test
  lives at a non-standard path will be missed.
- Deleted files are filtered out (`[ -f "$path" ]`).
- Directory selections hand the entire directory to pytest discovery.
- `--json` composes cleanly: the lane key is `"changed"` instead of the seven stable keys.

## Coverage: Full-Lane Only

The `--cov=astrid --cov-report=term --cov-report=xml --cov-fail-under=0` flags are
**only** active on the full `broad` lane when invoked without `--changed`. The `--changed`
fast path runs without coverage instrumentation to keep latency under 90 seconds.

## Marker Reference

| Marker | Meaning |
|--------|---------|
| `integration` | Requires external dependencies, heavyweight fixtures, or env prerequisites |
| `opt_in` | Explicitly opt-in; never runs in the default lane |
| `slow` | Slower integration-style tests; opt-in for tight loops |
| `renderer_parity` | Blocking semantic parity integration against packaged renderer fixtures |
| `standalone` | Test intended to run independently from the default suite |
| `hype_cut_invariants` | Standalone hype cut invariant coverage |

## Adding new opt-in tests

1. Add `@pytest.mark.integration` and `@pytest.mark.opt_in` to the test function.
2. If the test has existing specific markers (e.g., `renderer_parity`, `standalone`),
   preserve them alongside the new markers.
3. Add the prerequisite check as a `pytest.skip` or `@pytest.mark.skipif` inside the
   test — this is only exercised when the test is explicitly collected via an opt-in lane.
4. Update the `QUARANTINE_TESTS` array in `run_ci_checks.sh` if the test is
   quarantine-eligible.
