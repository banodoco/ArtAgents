# SDK extended-composition propagation fix

Date: 2026-08-24  
Severity: P1 (fixed)

## Reproduction

An agent can intentionally compose a long-lived client with an extended
schema-pack registry:

```python
with AstridClient.open(root, registry=core_plus_standard_plus_runaway) as client:
    client.projects.create(slug="extended-lab", name="Extended Lab")
    client.invoke("rendering.timeline_visualize", kind="executor", ...)
```

The project and timeline writes used the injected registry, but the old
`astrid.sdk.invoke` path rebuilt `build_standard_registry()` inside
`_kernel_invoke`. Once the client database had the `runaway` migration, the
second composition correctly raised an unregistered-migration error. The
client therefore failed its own built-in capability invocation despite having
the exact valid registry that opened the store.

## Fix

The exact schema registry is now retained through the complete long-lived SDK
path:

* `AstridClient.invoke` and `invoke_result` pass the bound application
  registry;
* `sdk.invoke` and `_kernel_invoke` accept it and use it for the writer,
  events, repositories, admission, and completion instead of rediscovering a
  narrower standard composition;
* retry services retain the registry and pass it to retry dispatch;
* `kernel/read.py` has a context-scoped registry for nested in-process
  capability reads, while still accepting an explicit registry for direct
  callers;
* the in-process capability handler scopes the bound projects root, so a
  client opened with an explicit root does not depend on ambient
  `ASTRID_PROJECTS_ROOT` during nested execution;
* canonical `.astrid/astrid.sqlite3` is preferred over a coexisting legacy
  `kernel.sqlite3` shim.

Default CLI/module-level behavior remains unchanged: absent an explicit
registry, the standard in-tree composition is built. `extra_pack_roots`
continues to control capability discovery only; it does not silently register
arbitrary schema migrations.

Explicit incomplete registries still fail closed. Reopening a pack-backed
database with `core_only_registry()` raises `MigrationTooNewError`; migration
safety is not weakened or bypassed.

## Focused guards

Added/updated focused tests:

* `tests/sdk/test_extended_composition.py` exercises a real long-lived client
  with the `runaway` migration, creates a project and canonical timeline,
  invokes `rendering.timeline_visualize`, reads the run back through
  `client.runs.list`, and asserts all five migration packs are present;
* the same test proves an explicit core-only registry is rejected;
* `tests/v10/test_kernel_read_composition.py` proves standard pack reads,
  explicit incomplete-registry rejection, and canonical-store preference over
  a legacy shim.

Focused result:

```
python3 -m pytest -q \
  tests/sdk/test_extended_composition.py \
  tests/v10/test_kernel_read_composition.py \
  tests/sdk/test_tasks.py tests/sdk/test_runs.py
43 passed
```

## Fresh live proof

Disposable root: `/private/tmp/astrid-sdk-extended-9UNts5`.

The public Python SDK opened one client with core + timeline + shots +
references + runaway, created `extended-lab` and its default canonical
timeline, invoked `rendering.timeline_visualize` through that same client,
and read the resulting run back through `client.runs.list`:

```
invoke_ok=True, runs_ok=True, run_count=1
schema_migrations = core, references, runaway, shots, timeline
```

The invocation returned a durable run ID and no error. The exact injected
registry survived the full writer/admission/handler/completion path.
