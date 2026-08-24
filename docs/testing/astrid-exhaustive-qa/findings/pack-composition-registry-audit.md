# Pack composition / migration-registry audit

Date: 2026-08-24  
Method: read-only construction audit, narrow database probes, one fresh public CLI replay, and one public SDK composition diagnostic  
Product-code changes by this auditor: none

## Verdict

The reported `applied migrations ... not registered in this composition` failure had one direct root cause: a reader opened the canonical standard project database with `core_only_registry()`. A normal Astrid database owns four migration identities (`core`, `references`, `shots`, and `timeline`), so the strict read-only compatibility probe correctly rejected the incomplete registry before returning a connection.

The concurrent correction in `astrid/core/kernel/read.py` changes the default read composition to the full standard registry and permits an already-composed registry to be supplied explicitly. A fresh public `timelines visualize --from-view ...` replay now succeeds. The strict migration probe should remain strict; weakening it would turn a deterministic authority error into undefined reads.

Two composition boundaries remain important:

1. `AstridClient.open(..., registry=<extended>)` accepts an extended schema composition, but the client's lazy `invoke()` path does not propagate that registry. `_kernel_invoke()` reconstructs the fixed standard registry and fails against the same extended database. This was reproduced with the tracked optional `runaway` schema pack.
2. Kernel read-path selection still checks legacy `<projects_root>/kernel.sqlite3` before canonical `<projects_root>/.astrid/astrid.sqlite3`. If both exist, the helper can silently select a different ledger. This did not affect the fresh canonical replay, but it is an authority ambiguity worth closing separately.

## Required invariant

> Every open or compatibility probe of one database must receive one complete frozen registry containing every pack that owns an applied migration in that database.

Consequences:

- The default composition for `${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3` is the full standard registry: `core + references + shots + timeline`.
- `core_only_registry()` is valid only for a deliberately separate core-only database whose migration ledger has never contained a domain pack.
- An extended composition must be bound to the application/client and propagated unchanged through invocation, read helpers, doctor, and backup/restore validation.
- External capability discovery must not be mistaken for schema composition. `extra_pack_roots` discovers executors/orchestrators/elements; it does not currently register schema-pack migrations.
- Unknown applied packs must continue to fail closed. Do not catch or ignore `MigrationTooNewError` to make packs appear optional.

## Exact root-cause evidence

A fresh canonical database created through the public CLI contained:

```text
applied [('core', 1), ('references', 1), ('shots', 1), ('timeline', 1)]
```

Opening that same file through the public store probe with the two compositions produced:

```text
core_only MigrationTooNewError database contains applied migrations for pack 'references', which is not registered in this composition
standard OK
```

Before the concurrent correction, both `kernel_run_info()` and `kernel_runs_for_project()` called `open_database(..., core_only_registry(), read_only=True)` against the canonical database. `open_database()` deliberately runs `probe_database()` for both writable and read-only opens, so the error occurs before a connection is returned. The helpers caught SQLite/file errors but not migration incompatibility, allowing this registry mismatch to escape through otherwise valid user operations.

The corrected helper now defaults to `astrid.core.schema_packs.standard.build_standard_registry()` and exposes an optional `registry=` only for a caller that already owns an explicit composition.

## Construction matrix

| Construction/open site | Database | Registry | Public reachability | Audit result |
|---|---|---|---|---|
| `compose_standard_application()` / `open_standard_writer()` | `.astrid/astrid.sqlite3` | fixed standard unless explicitly injected | Top-level domain CLI, `AstridClient.open()`, projects/timelines/media/tasks/runs/references/shots | Correct for the standard store. An injected extension remains coherent for bound domain services. |
| `compose_standard_bridge()` | `.astrid/astrid.sqlite3` | fixed standard unless explicitly injected | `astrid serve` bridge composition | Correct for standard composition. |
| `sdk.invocation._kernel_invoke()` | `.astrid/astrid.sqlite3` | reconstructs fixed standard every call | Public executor/orchestrator invocation; canonical render and visualize | Correct on a standard DB; incompatible with a client/application that previously wrote an extended migration. |
| `core.kernel.read` (after concurrent fix) | first existing candidate, normally `.astrid/astrid.sqlite3` | full standard by default; explicit registry accepted | Frozen-view preflight/load, attached renders, run guidance/listing, worker baseline lookup | Registry mismatch corrected. Legacy-first path selection remains ambiguous if two DBs coexist. |
| `core.rendering.assets._owned_managed_locators()` | `.astrid/astrid.sqlite3` | fixed standard | Managed media resolution for render inputs | Correct for standard DB; same extension caveat. |
| Doctor schema probe | `.astrid/astrid.sqlite3` | fixed standard | `astrid doctor` | Correct for standard DB; reports an intentionally extended DB as incompatible. |
| Backup staged-database validation | staged canonical DB | fixed standard | backup/restore validation | Correct for standard DB; rejects an intentionally extended backup unless extension composition is propagated. |
| `project.kernel_admission` | legacy `<root>/kernel.sqlite3` | core-only | Direct module `main()` admission shims for hype, event_talks, and thumbnail_maker | Does not trigger the exact error while it remains a truly separate core-only DB, but creates a second ledger and the coexistence hazard. Public SDK invocation normally bypasses these `main()` shims. |
| Timeline/frozen selector helpers using raw `sqlite3` | `.astrid/astrid.sqlite3` | none | Managed timeline selection and some visualization reads | Cannot emit the exact registry error because no migration probe runs; has ordinary schema-coupling risk instead. |
| `CapabilityTaskHandler` with `extra_pack_roots` | caller's already-open writer/UoW | no new registry | External executor/orchestrator runtime | Safe from this exact mismatch. It scopes `ASTRID_PACKS_PATH`; it does not open or migrate another DB. |

## Public paths affected by the original incomplete reader

The two kernel-read helpers feed more than run-list presentation:

- `timelines visualize --from-view <manifest> --focus ...` authority preflight in `core/contracts/timeline_visualize.py`.
- Frozen visualization reconstruction in `packs/rendering/executors/timeline_visualize/frozen.py`.
- Attached rendering provenance in `core/rendering/attached.py`, used by cut, hype, iteration-video, and human-notes workflows.
- Run guidance/listing in `core/project/guidance.py` and the legacy project facade.
- Banodoco worker baseline stamping.

Most of these callers catch `sqlite3.Error`, not `MigrationTooNewError`, so the mismatch was capable of turning valid canonical state into a top-level failure rather than merely omitting optional metadata.

## Fresh public CLI replay after the correction

Disposable root: `/tmp/astrid-pack-registry-audit.UTug3s/projects` (removed after evidence capture).

A project named `audit` and canonical timeline `main` were created through the public CLI. A normal visualization succeeded with kernel run:

```text
aee4ca4ebd7347c1cd41563b61
```

Its durable manifest was returned from managed CAS:

```text
/private/tmp/astrid-pack-registry-audit.UTug3s/projects/.astrid/media/sha256/15/e3/15e3d4405996c39fbe6181ee054bddea1f0eece716efff1beaa656d592732fbc
```

That exact returned CAS path was then used through the documented public route:

```bash
python3 -m astrid timelines visualize \
  --project audit \
  --from-view <returned-manifest-CAS-path> \
  --focus TL01 \
  --format md \
  --layout linear \
  --filmstrip off \
  --json
```

The command exited 0 and admitted/completed run `67614affd5ccae251d0f767564`. Direct read-helper diagnostics returned the first visualization's canonical run data and both project run IDs. This is the user path that previously encountered the incomplete registry.

## External pack roots versus extended schema registries

These are different mechanisms and should remain explicit:

- `extra_pack_roots` participates in capability/model discovery and is copied into task specs. During execution, `CapabilityTaskHandler` scopes those roots into `ASTRID_PACKS_PATH` and uses the already-created task service/writer. There is no external schema-pack discovery or database composition step in this route.
- `registry=` on `AstridClient.open()` changes the database composition itself. That registry can legitimately apply migrations beyond the standard four, but every subsequent opener of that database must receive it.

The long-lived public SDK boundary was reproduced as follows:

1. Build a frozen registry containing `core`, `references`, `shots`, `timeline`, and tracked optional pack `runaway`.
2. `AstridClient.open(fresh_root, registry=extended)`.
3. `client.projects.create(slug="extended", ...)` returned `ok=True` and applied all five pack migrations.
4. `client.invoke("media.gif_search", kind="executor", project="extended", ...)` failed before capability execution.

Exact result:

```text
invoke_error_type CapabilityInvocationError
invoke_error failed to invoke executor 'media.gif_search'
cause_type MigrationTooNewError
cause database contains applied migrations for pack 'runaway', which is not registered in this composition
```

This is a genuine composition-propagation defect if injected registries are a supported public SDK contract. The bounded solutions are either:

- propagate the bound frozen registry from `AstridClient` through `invoke()` / `_kernel_invoke()` and all other probes of its database; or
- explicitly make custom schema composition unsupported at the public client boundary and reject it before any extended migration is written.

Silently rebuilding a narrower registry after accepting the extended one is not safe.

## Legacy database precedence

`core.kernel.read._db_path()` currently checks candidates in this order:

1. `<root>/kernel.sqlite3`
2. `<root>/.astrid/astrid.sqlite3`
3. `<root>/.astrid/kernel.sqlite3`
4. `<root>/astrid.sqlite3`

Meanwhile, `project.kernel_admission` still creates the first path with a core-only registry. A root containing both that legacy database and the canonical standard database therefore directs kernel readers to the legacy ledger. The immediate registry fix is correct for the canonical case, but candidate ordering should prefer the canonical path, or coexistence should fail with actionable authority guidance. Otherwise run provenance/listing can be sourced from the wrong store without a migration error.

## Narrow checks

Post-fix reader and selection checks:

```text
python3 -m pytest -q \
  tests/v10/test_kernel_read_composition.py \
  tests/v10/test_selection_isolation.py

2 passed in 0.08s
```

Composition guards:

```text
python3 -m pytest -q \
  tests/v10/test_kernel_read_composition.py \
  tests/v10/test_standard_application.py::test_composed_database_is_exactly_the_frozen_catalog \
  tests/v10/test_standard_application.py::test_composition_and_event_repository_do_no_dynamic_discovery \
  tests/v10/test_registry.py::test_standard_composition_registers_exactly_three_packs \
  tests/v10/test_registry.py::test_standard_composition_declares_the_fixed_pack_order \
  tests/v10/test_registry.py::test_standard_composition_has_no_discovery_beyond_in_tree_manifests

5 passed, 1 failed
```

The one failure is an existing guard drift, not caused by this audit: the test glob now discovers tracked `astrid/packs/runaway/schema-pack.yaml` in addition to references/shots/timeline, while both standard registry builders intentionally enumerate exactly the three standard domain packs. The test name/assertion should distinguish “files present in tree” from “packs explicitly selected into the standard composition.” It should not be weakened into dynamic discovery.

## Recommended follow-up guards

1. Keep the new canonical-reader regression: a database with all four standard migrations must be readable by default, while an explicitly supplied core-only registry must still fail closed.
2. Add parity coverage between `astrid.packs.build_standard_registry()` and `astrid.core.schema_packs.standard.build_standard_registry()` over pack IDs and migration descriptors/checksums. The duplicated explicit tuples are intentional, but drift between them recreates this class of failure.
3. Add a long-lived client test: when a client is opened with an accepted extended registry, bound invocation either receives the same registry or is rejected before extended migration/application creation.
4. Add a coexistence test for legacy `kernel.sqlite3` plus canonical `.astrid/astrid.sqlite3`; canonical public reads must never silently select the legacy ledger.
5. Keep the compatibility probe strict for unknown applied packs.

## Cleanup

All disposable extended-registry diagnostics were deleted immediately after each run. The public CLI replay root was removed after recording the durable IDs and migration evidence. No Astrid, renderer, or audit subprocess was left running.
