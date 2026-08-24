# First-run doctor and selection isolation fix

Date: 2026-08-24

## Scope and verdict

Independent live agent-UX replay covered two first-run P2s using only public
CLI/help for reproduction, followed by bounded implementation and a fresh
public replay:

1. a pristine `doctor --json` looked red even though the root had simply never
   been initialized;
2. workspace project selection was written to the checkout's
   `.astrid/config.json`, so two `ASTRID_PROJECTS_ROOT` values launched from
   the same checkout overwrote each other's workspace routing preference.

**PASS.** A pristine root now reports `state: "uninitialized"`, `ok: true`,
and exit 0 with the create-project recovery. An initialized healthy root
reports `state: "ready"`; a real missing/corrupt store still reports
`state: "unhealthy"`, `ok: false`, and exit 1. With `ASTRID_PROJECTS_ROOT`
set, default workspace preferences now live under that root, while explicit
`--cwd` remains available for an intentional alternate workspace boundary.

## Original black-box evidence

Fresh roots were created as `/tmp/astrid-first-run-a-dd6nbK` and
`/tmp/astrid-first-run-b-QIrJUa`, from the Astrid checkout.

### Doctor friction

On the untouched first root, public `astrid doctor --json` returned `ok:false`
and exit 1. `data_paths`, `sqlite_quick_check`, `fk_integrity`, and
`schema_versions` all reported `fail` because `.astrid/astrid.sqlite3` did not
exist. Each detail did say this was expected on a brand-new root, but the
overall red result contradicted the documented doctor-first journey and made
an agent investigate a non-failure.

After `projects create`, the same doctor checks became green as expected.
Deleting the database from an existing `.astrid` directory remained a genuine
fail-closed case; this distinction is preserved by the fix.

### Selection leak

With root A's project `alpha` selected, the public result reported:

```json
{
  "selection": {
    "ref": "alpha",
    "scope": "workspace",
    "path": "/Users/peteromalley/Documents/reigh-workspace/Astrid/.astrid/config.json"
  }
}
```

Root B then selected `beta`, writing the same checkout path. `projects
current` in root A subsequently read `beta` and failed closed because `beta`
did not exist in root A. This was a real cross-root routing leak. The
workspace path was ambient checkout state even though the kernel root was
explicitly isolated.

The first replay also surfaced an existing user-scope preference in the
developer home. That scope is intentionally global; the independent proof
below uses a fresh `ASTRID_HOME` so workspace isolation is tested without
ambient user preference state.

## Bounded implementation

### Doctor state model

`astrid/core/doctor.py` now distinguishes three truthful states:

- `uninitialized`: no `.astrid` store exists yet; relevant checks have status
  `uninitialized`, are non-required, and include the exact create recovery;
- `ready`: initialized root and all checks pass;
- `unhealthy`: any real failed check, including a missing database inside an
  existing `.astrid` directory, migration incompatibility, corruption, or
  integrity failure.

The JSON payload adds `state` while preserving `ok` and the existing checks.
The human output prints the state. Optional media warnings retain their prior
strict/non-strict behavior.

### Selection boundary

`workspace_config_path()` now uses `ASTRID_PROJECTS_ROOT/.astrid/config.json`
when the projects-root environment is set and no explicit `cwd` is supplied.
The explicit `ASTRID_WORKSPACE_CONFIG_DIR` override and `--cwd` behavior remain
unchanged. CLI help and the core/getting-started/debugging guides describe this
precedence and the intentional global `--scope user` alternative.

## Fresh live proof after the fix

Fresh roots:

- A: `/tmp/astrid-first-run-proof-a-EEYT7K`
- B: `/tmp/astrid-first-run-proof-b-x4eouy`
- isolated user state: `/tmp/astrid-first-run-proof-home-*`

Public results:

1. pristine A: `doctor --json` returned `ok:true`, `state:"uninitialized"`,
   exit 0; all four not-yet-created store checks were explicitly
   `status:"uninitialized"` with the create command. No files were repaired
   or created by doctor.
2. after A's `projects create`: doctor returned `ok:true`,
   `state:"ready"`, with all required checks `ok`.
3. A selected `alpha`; the returned workspace path was
   `/tmp/astrid-first-run-proof-a-EEYT7K/.astrid/config.json`.
4. B's `projects current` before selection returned the typed
   `no_current_project` recovery, not A's selection.
5. B selected `beta`; its path was
   `/tmp/astrid-first-run-proof-b-x4eouy/.astrid/config.json`.
6. B's `current` resolved `beta`, and A's `current` still resolved `alpha`.

The durable files contained independent values:

```text
/tmp/astrid-first-run-proof-a-EEYT7K/.astrid/config.json -> {"default_project":"alpha"}
/tmp/astrid-first-run-proof-b-x4eouy/.astrid/config.json -> {"default_project":"beta"}
```

## Guards

Focused checks:

```text
python3 -m pytest -q \
  tests/v10/test_doctor.py \
  tests/v10/test_selection_isolation.py \
  tests/sdk/test_projects.py \
  tests/v10/test_m6_gate.py -k 'doctor or selection or project'
```

This focused selection/doctor slice passed (31 passed, 5 deselected); the
doctor gate still asserts that an existing root with a deleted database is
`state:"unhealthy"` and fails closed. A full `tests/v10/test_m6_gate.py` run
also exercises the repository-wide authority lint, which currently reports
pre-existing unrelated SQLite-construction findings in other dirty files; that
lint failure is outside this bounded change. The selection guard proves two
roots can hold independent workspace defaults while an explicit user/home
scope is left intentional.
