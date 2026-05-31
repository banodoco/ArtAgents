# Sprint 0 — Prerequisites Operator Surface

This directory is the Sprint 0 runbook for the reshape epic. It intentionally
documents one operator surface only; compatibility scripts must delegate here
instead of preserving older single-root behavior.

## Canonical Surface

| Concern | Canonical value |
| --- | --- |
| Sprint branch | `reshape-s0-prerequisites` |
| Snapshot command | `python3 -m scripts.reshape.snapshot_state --projects-root <projects-root> --repo-root <repo-root> --out-dir <snapshot-dir>` |
| Inventory command | `python3 -m scripts.reshape.inventory_state --projects-root <projects-root> --repo-root <repo-root> --out <inventory.csv>` |
| Restore rehearsal command | `python3 -m scripts.reshape.restore_rehearsal --snapshot <snapshot.tar.gz> --out-dir <restore-dir>` |
| Migration gate command | `python3 -m scripts.reshape.migration_gate --snapshot <snapshot.tar.gz> --migration-cmd '<command with {projects_root} and {repo_root}>' --out <gate.json>` |
| Sprint 0 handoff | `docs/reshape/sprint-0-handoff.md` |
| Decisions record | `docs/reshape/decisions.md` |

The existing compatibility entrypoints remain only for muscle memory:

```bash
bash scripts/snapshot_astrid_projects.sh --projects-root <projects-root> --repo-root <repo-root> --out-dir <snapshot-dir>
python3 scripts/inventory_astrid_projects.py --projects-root <projects-root> --repo-root <repo-root> --out <inventory.csv>
```

Both wrappers delegate to the canonical `scripts.reshape.*` modules. They must
not retain projects-root-only behavior.

The original planned branch name was `reshape/sprint-0`, but this repository
already has a local branch named `reshape`, which occupies `refs/heads/reshape`
and prevents creating child refs under `reshape/*`. Sprint 0 therefore uses the
existing long-lived branch `reshape-s0-prerequisites` as the canonical branch.

## Rollback Scope

Rollback and inventory cover the same declared multi-root state surface:

- The projects root: legacy `active_run.json` only as migration input when
  present, current `current_run.json`, per-run `lease.json`, per-run
  `events.jsonl`, timelines, `plan.json`, `audit/ledger.jsonl`,
  `hype.plan.json`, and `_llm_debug/`.
- The repo root rollback subset: `.astrid/threads.json`,
  `.astrid/threads/**/groups.json`, `.astrid/threads/**/selections.jsonl`, and
  discovered `.astrid.variants.json` sidecars.

The snapshot artifact is a tarball outside the repository with stable top-level
sections:

```text
projects/
repo/
```

Unrelated repository source contents are not part of rollback state.

## Migration Gate Contract

Migration gates run against extracted copies of both declared roots. A migration
command is acceptable only when it targets both temp roots by one of these
contracts:

- It contains both `{projects_root}` and `{repo_root}` placeholders.
- It matches a known safe injector that supplies both extracted roots explicitly.

Commands that target only one root, rely on ambient sessions, or can mutate live
state are rejected. Gate comparisons use inventory rows with root-relative paths
only; absolute temp paths must not enter comparable CSV output.

## Decisions

See `docs/reshape/decisions.md` for the Sprint 0 decisions that later batches
must follow:

- V1 pack trust boundary.
- Component manifest loading policy before `schema_version` edits.

## Sprint 0 Handoff

The Sprint 0 handoff for Sprint 1 is `docs/reshape/sprint-0-handoff.md`. It
names the committed inventory, external snapshot manifest, restore rehearsal
result, migration-gate and two-tab command contracts, pinned regression status,
CI status, manifest-loading policy, session-helper caveat, and reviewer
checklist. It is limited to Sprint 0 prerequisites and does not claim later
sprint migrations or reshape behavior are complete.

Retired reshape planning inputs are not current operating guidance. Sprint 0
handoff docs preserve only the implementation evidence needed to replay or
audit that sprint.

## Sprint 0 Deliverables

| # | Deliverable | File Location |
|---|------------|---------------|
| 1 | Branch | `reshape-s0-prerequisites` |
| 2 | Snapshot compatibility wrapper | `scripts/snapshot_astrid_projects.sh` |
| 3 | Inventory compatibility wrapper | `scripts/inventory_astrid_projects.py` |
| 4 | Inventory baseline CSV | `docs/reshape/inventory-baseline-YYYYMMDD.csv` |
| 5 | Two-tab harness | `tests/concurrency/two_tab_harness.py` |
| 6 | Harness smoke test | `tests/concurrency/test_two_tab_harness_smoke.py` |
| 7 | Env inheritance spike | `tests/spikes/test_env_inheritance.py` |
| 8 | Env inheritance findings | `docs/reshape/spike-env-inheritance.md` |
| 9 | Flock-on-APFS spike | `tests/spikes/test_flock_apfs.py` |
| 10 | Flock-on-APFS findings | `docs/reshape/spike-flock-apfs.md` |
| 11 | Regression workload | `docs/reshape/regression-workload.md` |

## Local CI

```bash
# Install the same dependency set used by GitHub Actions (core + dev via the [dev] extra).
python3 -m pip install -e '.[dev]'

# Run the local mirror of .github/workflows/ci.yml.
bash scripts/reshape/run_ci_checks.sh
```

Private/local pack dependencies (e.g. `runpod-lifecycle`, `pyannote.audio`) are
intentionally excluded and stay optional — install them separately as documented
in `pyproject.toml` and the relevant pack `requirements.txt` files.

To validate a brand-new clone end-to-end (isolated venv, dependency install,
then `python -m astrid doctor --json`):

```bash
bash scripts/smoke_fresh_clone.sh
```

The local CI mirror runs:

- `python3 -m ruff check .` scoped by `pyproject.toml` to Sprint 0 Python surfaces
- `python3 -m mypy scripts/reshape`
- `python3 -m pytest tests/reshape -q`
- `python3 -m pytest tests/reshape/test_hype_regression_fixture.py -q`
- `python3 -m pytest tests/concurrency/test_two_tab_harness_smoke.py -q`
- a broad pytest pass that excludes the currently known unrelated baseline
  failure files and avoids network-heavy gates.

## Related Docs

- `docs/reshape/decisions.md` — Sprint 0 operator decisions.
- `docs/reshape/sprint-0-handoff.md` — Sprint 0 handoff inventory for Sprint 1.
- `docs/reshape/spike-env-inheritance.md` — Results of the env inheritance audit.
- `docs/reshape/spike-flock-apfs.md` — Results of the flock-on-APFS spike.
- `docs/reshape/regression-workload.md` — Pinned regression workload baseline.
