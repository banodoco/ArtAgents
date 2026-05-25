# Sprint 0 Handoff

This is the Sprint 0 handoff inventory for Sprint 1. It records the safety
surface and validation artifacts produced by Sprint 0 only. It does not claim
that later sprint migrations, task-mode reshapes, or Sprint 1 behavior have
been executed.

## Artifacts

| Item | Value |
| --- | --- |
| Inventory CSV | `docs/reshape/artifacts/sprint-1-handoff-inventory.csv` |
| Inventory size | 9 rows, 1884 bytes |
| Snapshot manifest | `docs/reshape/artifacts/sprint-1-handoff-snapshot-manifest.json` |
| Multi-root snapshot tarball | `/private/tmp/astrid-snapshots/astrid-state-20260524-042125.tar.gz` |
| Snapshot SHA-256 | `19c565d09bba44cb03be5c4652fc79baddf589df4bd40b000c250e4dbebc7b22` |
| Snapshot commit policy | The tarball is external because it contains project artifacts and debug payloads; the committed manifest carries the path, checksum, and coverage proof. |
| Projects root used | `/Users/peteromalley/Documents/reigh-workspace/astrid-projects` |
| Repo root used | `/Users/peteromalley/Documents/reigh-workspace/Astrid` |
| Canonical branch | `reshape-s0-prerequisites` |

The snapshot manifest records stable `projects/` and `repo/` top-level roots.
The committed inventory uses only root-relative paths.

The planned branch name `reshape/sprint-0` could not be created because the
repository already has a local branch named `reshape`, which blocks the
`refs/heads/reshape/*` namespace. The existing branch
`reshape-s0-prerequisites` is the canonical Sprint 0 branch for this handoff.

## Covered State Surface

Sprint 0 rollback and inventory intentionally cover the same multi-root state:

- Projects-root state: legacy `active_run.json` only as migration input when
  present, `current_run.json`, per-run `lease.json`, per-run `events.jsonl`,
  timelines, `plan.json`, `audit/ledger.jsonl`, `hype.plan.json`, and
  `_llm_debug/`.
- Repo-root rollback subset: `.astrid/threads.json`,
  `.astrid/threads/**/groups.json`, `.astrid/threads/**/selections.jsonl`, and
  discovered `.astrid.variants.json` sidecars.

The T19 handoff snapshot included 41 project files and 1 repo-state file when
rehearsed into `/private/tmp/astrid-restore-rehearsal-dir6PR`.

## Commands

Inventory:

```bash
python3 -m scripts.reshape.inventory_state \
  --projects-root /Users/peteromalley/Documents/reigh-workspace/astrid-projects \
  --repo-root /Users/peteromalley/Documents/reigh-workspace/Astrid \
  --out docs/reshape/artifacts/sprint-1-handoff-inventory.csv
```

Snapshot:

```bash
python3 -m scripts.reshape.snapshot_state \
  --projects-root /Users/peteromalley/Documents/reigh-workspace/astrid-projects \
  --repo-root /Users/peteromalley/Documents/reigh-workspace/Astrid \
  --out-dir /private/tmp/astrid-snapshots \
  --timestamp 20260524-042125
```

Restore rehearsal result:

```bash
python3 -m scripts.reshape.restore_rehearsal \
  --snapshot /private/tmp/astrid-snapshots/astrid-state-20260524-042125.tar.gz \
  --out-dir /private/tmp/astrid-restore-rehearsal-dir6PR
```

The rehearsal completed read/copy-only, with `project_file_count=41` and
`repo_state_file_count=1`. Live restore remains gated behind explicit
`--target-projects-root`, explicit `--target-repo-root`, and
`--destructive-restore`.

Migration gate command shape:

```bash
python3 -m scripts.reshape.migration_gate \
  --snapshot <snapshot.tar.gz> \
  --migration-cmd 'python3 <migration.py> --projects-root {projects_root} --repo-root {repo_root}' \
  --out <gate.json>
```

The command-targeting contract is strict: commands must target both extracted
roots through `{projects_root}` and `{repo_root}` placeholders, or use a known
safe dual-root injection path. Commands that target only one root, depend on
ambient sessions, or can mutate live projects or repo-root `.astrid` state are
rejected.

Two-tab harness command shape:

```bash
python3 -m scripts.reshape.two_tab_harness \
  --projects-root <isolated-projects-root> \
  --astrid-home <isolated-astrid-home> \
  --session-id <session-id> \
  --command '<child command>' \
  --expected-winner-count 2
```

The wrapper creates or accepts isolated roots and sets `ASTRID_PROJECTS_ROOT`,
`ASTRID_HOME`, session, run, task, and writer environment for both children.
Heavy append races remain opt-in through `ASTRID_HEAVY_APPEND_RACES=1`.

## Validation Status

T19 ran cheap-to-broad validation. The local CI mirror passed:

```bash
bash scripts/reshape/run_ci_checks.sh
```

The mirror includes Ruff, configured mypy for `scripts/reshape`, Sprint 0
pytest, pinned hype regression smoke, two-tab harness smoke, and a broad pytest
subset that excludes known unrelated baseline failures. Ruff is intentionally
scoped in `pyproject.toml` to Sprint 0 Python surfaces; the pre-existing
repository-wide Ruff backlog is not part of Sprint 0.
On GitHub Actions, the broad pytest subset also excludes tests that require
uncommitted local fixtures, real FAL credentials, ffprobe, or the sibling
timeline-composition checkout.

Pack validation passed:

```bash
python3 -m astrid packs validate astrid/packs/builtin --warnings
```

The only output was recommended-file warnings for builtin-pack `AGENTS.md` and
`README.md`.

Full unfiltered pytest was also rerun. It still failed with 11 baseline
failures in model-catalog, dataset-build offline fixtures, and author-test
golden/drift tests; no new Sprint 0 failure was identified by T19 or the
post-review verification pass.

`idea.md` and `docs/reshape/review-findings.md` were protected pre-existing
reshape planning inputs in the worktree before Sprint 0 execution began. Sprint
0 used them as read-only planning context and does not claim their diffs as S0
implementation output.

Targeted validation passed for:

- Snapshot, restore rehearsal, inventory, and migration gate tests.
- Two-tab wrapper and locked append tests.
- Env-inheritance and production-lock spike fixture tests.
- Component manifest parser parity, orchestrator schema, builtin pack
  validation, pack YAML/schema CLI, element registry/CLI, and fork tests.
- Shared helper deduplication tests for time, env/secrets, and duration-only
  media probing plus affected pack tests.
- `REPO_ROOT` regressions for element CLI project-local state and executor
  install path calculation.
- Repo hygiene guard and `git diff --check`.

## Regression State

The pinned hype regression fixture lives at
`tests/fixtures/reshape/hype_regression/` and is documented in
`docs/reshape/hype-regression.md`.

Small JSON fixtures are committed and validated. Large media is intentionally
not committed. When `main.mp4` and `broll.mp4` are absent, the media-dependent
render assertions skip by design; the smoke still fails if required small JSON
fixtures are missing or malformed.

## Manifest Loading Policy

DEC-002 in `docs/reshape/decisions.md` is the settled Sprint 0 policy:

- Runtime component manifest loaders and pack validation share one
  YAML-aware parser.
- `.json` manifests use strict JSON parsing.
- `.yaml` and `.yml` manifests use `yaml.safe_load`.
- First-party builtin executor, orchestrator, and element manifests that are
  schema-checked carry explicit `schema_version: 1`.
- Parser parity tests prove direct JSON Schema validation, pack validator
  loading, and runtime registry/parser loading agree for checked builtin
  manifests.

## Session Helper Caveat

Sprint 0 consolidated duplicated session test scaffolding only. The shared
callable fixtures are `mint_session`, `seed_project`, and `seed_project_run` in
`tests/conftest.py`. The follow-up search found no remaining local definitions
or call sites for `_mint_session`, `_seed_session`, `_seed_project`,
`_setup_project`, or `_seed_project_with_run` under `tests/session/`.

This was a test-helper cleanup, not a runtime session model migration.

## Reviewer Checklist

- Deterministic output: inventory rows are sorted, root-relative, and include
  `root_kind,project_slug,run_id,state_kind,relative_path,size_bytes,mtime_ns,sha256`.
- Explicit root arguments: snapshot, inventory, restore rehearsal, migration
  gate, and two-tab harness commands name projects root and repo root or an
  isolated equivalent explicitly.
- Tempdir and copy defaults: restore rehearsal extracts to temp/explicit output
  and remains read/copy-only unless both target roots and
  `--destructive-restore` are present.
- Ambiguous-command rejection: migration gate rejects commands that do not
  prove both extracted roots are targeted.
- Root coverage: the snapshot and inventory include the declared projects-root
  state and the repo-root `.astrid` thread/variant rollback subset only.
- Repo hygiene: generated root reports, tracked `.desloppify/`, and tracked
  `*.bak` artifacts are guarded by `scripts/reshape/check_repo_hygiene.py`.
