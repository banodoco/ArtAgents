# Replay: first-run and selection isolation 2

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` CLI/help only  
Verdict: **PASS — 9.8/10; no P0/P1 findings.**

Two fresh roots from the same checkout were exercised without `--cwd`:

- root A: `/tmp/astrid-select-A-34cYWv`
- root B: `/tmp/astrid-select-B-nKpIjd`

## First-run and bootstrap

Before bootstrap, `ASTRID_PROJECTS_ROOT=<root> python3 -m astrid doctor
--json` returned exit 0 and `ok: true` in both roots. The checks were
explicitly typed `uninitialized` for data paths, SQLite, foreign keys, and
schema versions; media paths were optional/ok. No database or project was
silently created by doctor.

Public `projects create alpha --name Alpha` in A and `projects create beta
--name Beta` in B initialized each root. A subsequent doctor in both roots was
fully green: accessible data paths, managed media, SQLite quick check, no
foreign-key violations, and all schema versions present.

## Selection isolation

Without `--cwd`:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-select-A-34cYWv \
  python3 -m astrid projects select alpha --json
ASTRID_PROJECTS_ROOT=/tmp/astrid-select-B-nKpIjd \
  python3 -m astrid projects select beta --json
```

Each `projects current --json` returned the root-local project and selection:

- A: `alpha`, selection path
  `/tmp/astrid-select-A-34cYWv/.astrid/config.json`
- B: `beta`, selection path
  `/tmp/astrid-select-B-nKpIjd/.astrid/config.json`

Each `projects list --json` exposed only its own project. The two config files
contained exactly their own defaults (`alpha` and `beta` respectively). A
checkout `.astrid/config.json` already existed before this replay; its SHA-256
and mtime were identical before and after repeated A/B `select` and `current`
calls, proving no checkout mutation or cross-root write during the replay.

## Corruption is not uninitialized

For a disposable copy of root A, the initialized SQLite file was moved aside
and replaced with non-SQLite bytes using an exact temporary target. Doctor
returned exit 1 and `ok: false`, reporting:

- managed-media inspection: `file is not a database`;
- SQLite quick check: `file is not a database`;
- foreign-key check: `file is not a database`;
- schema read: `file is not a database`.

The healthy original A root remained green afterward. The corrupt copy is
recoverable because the original database remains at
`/tmp/astrid-select-corrupt-X5U1Zj/.astrid/astrid.sqlite3.saved`.

## Remaining friction

No P0/P1 issue remains. A minor P2 usability opportunity is that first-run
doctor uses per-check `uninitialized` statuses but does not emit a separate
human guidance field; the statuses and exit-0 contract are nevertheless clear
and machine-actionable.

No source, test, or product files were edited for this replay; only this QA
report was added.
