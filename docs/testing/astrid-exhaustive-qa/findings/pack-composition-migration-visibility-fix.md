# Pack composition migration visibility fix

Date: 2026-08-24  
Severity: P1 (fixed)

## Reproduction

In a fresh public-CLI root, I created a project and canonical default
timeline, imported a fixture, created a `media references` row, and created a
`timelines shots` row. The database then correctly contained:

```
core=1, references=1, shots=1, timeline=1
```

The original failure was:

```
database contains applied migrations for pack 'references', which is not registered in this composition
```

It appeared when a capability later opened the canonical
`.astrid/astrid.sqlite3` through a kernel read helper. This was not a
too-new-schema condition: the database was healthy and the standard app
composition had already applied the references migration.

## Root cause

`astrid/core/kernel/read.py` opened canonical project databases with
`core_only_registry()`. That registry intentionally contains only core and is
valid for a standalone kernel-only database, but it cannot probe a canonical
Astrid project database after any pack-backed command has run. The migration
runner correctly rejected the unregistered `references` row; suppressing that
exception would have weakened schema safety.

## Fix

Kernel read helpers now default to the full standard schema composition from
`astrid.core.schema_packs.standard.build_standard_registry()`, which includes
the in-tree `timeline`, `shots`, and `references` packs. They also accept an
optional already-composed `FrozenSchemaPackRegistry` for callers using an
explicit extended composition. Supplying an intentionally incomplete
core-only registry still raises `MigrationTooNewError`, preserving the
too-new/unregistered migration guard.

The separate `project/kernel_admission.py` fallback still uses a standalone
`<projects-root>/kernel.sqlite3` core-only store. It is not the canonical
`.astrid/astrid.sqlite3` and was left unchanged.

## Focused regression

`tests/v10/test_kernel_read_composition.py` creates a standard migration DB,
proves both kernel read helpers can open it, and proves an explicitly supplied
core-only registry still fails closed. The focused test passes:

```
python3 -m pytest -q tests/v10/test_kernel_read_composition.py
1 passed
```

## Fresh live proof after the fix

Disposable root: `/private/tmp/astrid-pack-composition-MrKWp6`.

Public commands completed in order:

* `media references create --kind object --name Prop --media <managed id>`
* `timelines shots create --name Shot-1`
* `timelines visualize primary --format md --filmstrip off --json` → `ok: true`,
  durable run `48b8fc285d94746d537e0217d4`
* `timelines render primary --output-name composition-proof-after-fix.mp4
  --json` → `ok: true`, durable run `4423b06d39cd0e734439ac9958`
* `doctor --json` → `ok: true`, `state: ready`, schema versions show all four
  expected migrations.

The visualization and render outputs were published to managed CAS. No
migration safety checks were bypassed, and no external-pack registry was
silently merged into the standard composition.
