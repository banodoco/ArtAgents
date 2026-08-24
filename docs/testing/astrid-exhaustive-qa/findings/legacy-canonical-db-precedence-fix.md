# Legacy/canonical database precedence fix

Date: 2026-08-24  
Lane: live agent UX plus bounded implementation  
Verdict: **PASS after fix** (pre-fix authority ambiguity reproduced)  
Original severity: **P1 — wrong-ledger authority / provenance ambiguity**

## User contract

Astrid now applies one read-authority rule everywhere the historical database
layouts are supported:

1. If `<projects-root>/.astrid/astrid.sqlite3` exists, it is the sole read
   authority.
2. A historical database is a fallback only while the canonical database is
   absent. Historical fallback order is `<root>/kernel.sqlite3`,
   `<root>/.astrid/kernel.sqlite3`, then `<root>/astrid.sqlite3`.
3. Readers never merge rows from two ledgers.
4. Resolution itself is read-only. It never creates, migrates, renames, or
   removes either file.
5. `astrid doctor` names the selected and ignored paths. The diagnostic is an
   optional warning in normal mode and a failure under `--strict-optional`.

This preserves intentional legacy migration/readback without allowing the
mere presence of an older file to override the v10 canonical event ledger.

## Pre-fix live reproduction

I used only legitimate Astrid writers to manufacture distinct evidence; I did
not edit SQLite rows.

Canonical setup:

```console
$ export ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-precedence.bjEaYD
$ python3 -m astrid projects create canonical-project --name 'Canonical Project' --json
$ python3 -m astrid timelines create main --project canonical-project --name Main --default \
    --config '{"tracks":[{"id":"main","kind":"visual","label":"Main"}],"clips":[{"id":"canonical-only","at":0,"track":"main","clipType":"text","hold":1,"text":{"content":"CANONICAL","fontSize":32,"color":"#ffffff","align":"center"}}]}' \
    --registry '{"assets":{}}' --json
$ python3 -m astrid timelines visualize --project canonical-project \
    --timeline-slug main --layout linear --format md --filmstrip off --json
```

Canonical identities produced:

```text
project_id=f1fe7453-e8b8-5dfa-9101-71fba5cf8893
timeline_id=93f0b0f4-8d4c-595c-b2c5-5b0fa3f35ecc
timeline_ulid=kkwb9ymfnh99dxmdfh9ydybjjq
run_id=a4a2a6125889aa3c5e2c8cebd9
task_id=d3cf2d7a8d0e2990258e51750a
attempt_id=01m0stmpsmbmbsvr3es2db4m68
```

I then invoked the retained legacy admission writer
`admit_orchestrator_project_run(...)` against the same root, producing
`legacy-project` run `816ad6b67b593aa0808d8635c8` in
`<root>/kernel.sqlite3`.

Both legitimate ledgers then existed:

```text
/private/tmp/astrid-db-precedence.bjEaYD/.astrid/astrid.sqlite3  389120 bytes
/private/tmp/astrid-db-precedence.bjEaYD/kernel.sqlite3          253952 bytes
```

Before the fix, the shared kernel reader reported:

```text
selected /private/tmp/astrid-db-precedence.bjEaYD/kernel.sqlite3
canonical_runs []
legacy_runs ['816ad6b67b593aa0808d8635c8']
```

That is the bug: canonical state existed, but a historical file won solely
because it appeared first in a local candidate list.

## Implementation and consumer audit

The pure resolver lives in `astrid/core/kernel/database.py`. These read paths
now share it:

| Consumer | Why authority matters |
|---|---|
| `core.kernel.read` | run listing and run/task provenance |
| `core.rendering.assets` | project ownership authorization for managed CAS inputs |
| `core.project.project` | project-show run list versus historical filesystem fallback |
| `core.project.guidance` | project-selection run counts |
| `iteration.experiment_import` | whether imported evidence may claim kernel-derived authority |
| `core.doctor` | integrity, schema, media-locator checks and visible path diagnostics |

The experiment importer also stopped performing a raw query with
`project_id = project_slug`; it now uses `kernel_run_info`, which resolves the
canonical slug-to-project-ID boundary before stamping provenance.

The remaining direct canonical-path users were reviewed and intentionally
left alone: application startup/schema composition, backup/restore, managed
media relocation, and standard pack composition are canonical writers or
canonical-layout operations. `core.project.kernel_admission` remains the
intentional legacy writer whose output makes fallback/migration compatibility
possible.

## Post-fix live coexistence proof

```console
$ ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-precedence.bjEaYD \
    python3 -m astrid doctor --json
```

Relevant output:

```json
{
  "name": "data_paths",
  "status": "warn",
  "required": false,
  "detail": "canonical database selected: /private/tmp/astrid-db-precedence.bjEaYD/.astrid/astrid.sqlite3; ignored legacy database path(s): /private/tmp/astrid-db-precedence.bjEaYD/kernel.sqlite3. Complete the intended migration, then archive or remove legacy ledgers only after canonical data is verified."
}
```

The other database checks all inspected canonical state:

```text
sqlite_quick_check: quick_check ok
fk_integrity: no foreign key violations
schema_versions: core=1, references=1, shots=1, timeline=1
overall: ok=true, state=ready
```

Canonical public listing:

```console
$ ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-precedence.bjEaYD \
    python3 -m astrid runs list --project canonical-project --json
```

returned only canonical run `a4a2a6125889aa3c5e2c8cebd9`, with title and
input capability `rendering.timeline_visualize`. The legacy-only project did
not leak across authority boundaries:

```console
$ ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-precedence.bjEaYD \
    python3 -m astrid runs list --project legacy-project --json
{"data":null,"error":{"code":"not_found",...},"ok":false,...}
legacy-list-exit=1
```

Strict operators can turn coexistence into a failing health gate:

```console
$ ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-precedence.bjEaYD \
    python3 -m astrid doctor --json --strict-optional
strict-doctor-exit=1
```

The JSON preserved the exact selected/ignored path warning and reported
`ok=false`, `state=unhealthy`.

## Legacy-only fallback proof

A second fresh root was populated only through the retained legacy admission
writer:

```text
/private/tmp/astrid-db-legacy-reader.DPQwkX/kernel.sqlite3
```

The canonical kernel read surface immediately returned:

```text
runs=['dbabd629b46e8a170ce24cb78d']
run_info={
  'run_id': 'dbabd629b46e8a170ce24cb78d',
  'project_id': 'legacy-project',
  'status': 'running',
  'kind': 'orchestrator',
  'title': 'legacy.probe',
  'capability': 'legacy.probe',
  'task_id': '0b0eeecaa6a0348a8241fa5bb4'
}
```

Public read-only diagnostics remained usable:

```console
$ ASTRID_PROJECTS_ROOT=/private/tmp/astrid-db-legacy-reader.DPQwkX \
    python3 -m astrid doctor --json
```

Relevant output:

```text
data_paths: warn, required=false
legacy database fallback active: .../kernel.sqlite3;
canonical database is absent: .../.astrid/astrid.sqlite3
sqlite_quick_check: ok
fk_integrity: ok
schema_versions: core=1
overall: ok=true, state=ready
```

A filesystem listing after doctor contained only the legacy database (plus its
SQLite WAL/SHM companions). Doctor did not bootstrap canonical state.

One boundary is deliberate but worth documenting: normal stateful v10 CLI
startup composes/opens the canonical standard database. On a legacy-only root,
such a command may therefore create canonical state; from that moment the
canonical database is authoritative and legacy fallback ends. Migration
should be completed before normal stateful work begins. Doctor is the safe
first command for detecting this condition.

## Focused verification

```console
$ python3 -m pytest -q \
    tests/v10/test_kernel_database_precedence.py \
    tests/v10/test_kernel_read_composition.py \
    tests/v10/test_doctor.py
........                                                                 [100%]
8 passed in 7.20s

$ python3 -m pytest -q tests/core/rendering/test_assets.py \
    tests/v10/test_domain_cli_projects_timelines.py -x
........................................................................ [ 70%]
..............................                                           [100%]
102 passed in 7.02s

$ python3 -m pytest -q tests/packs/iteration/test_experiment_import.py
.................................                                        [100%]
33 passed in 1.60s
```

The new narrow guard creates independently seeded canonical and legacy
ledgers with distinct projects/runs, proves canonical-only selection under
coexistence, proves legacy-only fallback, and asserts exact doctor authority
diagnostics and canonical schema inspection.

## UX assessment

- **Fixed:** no silent wrong-ledger selection and no row merging.
- **Fixed:** managed-media authorization and imported-run provenance use the
  same authority as run/project readers.
- **Fixed:** doctor makes both coexistence and fallback explicit, including
  paths and a non-destructive recovery sequence.
- **Safe default:** normal doctor remains usable (`warn`, exit 0) during an
  intentional migration; CI/operators can opt into refusal with
  `--strict-optional`.
- **Residual friction (P3 documentation):** users with an old root need to run
  doctor before a stateful v10 command, because application bootstrap is
  itself the transition from legacy-only fallback to canonical authority.

No database was deleted, renamed, merged, or automatically migrated by this
fix.
