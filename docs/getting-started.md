# Getting Started with Astrid

Astrid is a Python SDK and harness toolkit for building and running
agentic UXes — pipelines where agents and humans collaborate to make art.

## Prerequisites

Astrid requires Python 3.11+. The clean-machine journey uses the checkout
directly; it needs no API keys, network access, or hosted service.

From the repository root, confirm the gateway is available:

```bash
python3 -m astrid --help
python3 -m astrid doctor --json
```

## Your First Command

From any shell, run the read-only health check:

```bash
python3 -m astrid doctor --json   # state=uninitialized on a pristine root
```

Other useful zero-secret commands:

```bash
python3 -m astrid doctor --json   # state=uninitialized on a pristine root
python3 -m astrid projects list --json
python3 -m astrid projects current --json  # inspect the selected project, if any
```

There is no configuration file and no hosted service. The projects root is
`ASTRID_PROJECTS_ROOT` (default `<repo>/projects` from a checkout), and the
first product command lazily creates the kernel store at
`$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3` — the SQLite database that the
product families read and write. `doctor --json` is the first diagnostic on a
clean machine. On a pristine root it reports `state: "uninitialized"` with
`ok: true` and the create-project recovery; after initialization it reports
`state: "ready"` when healthy and `state: "unhealthy"` only for a real
failure. It also reports `schema_versions`, media paths, SQLite quick-check,
and foreign-key status without repairing or rewriting data. A failing
`schema_versions` check means the database is newer or incompatible with this
checkout; preserve the database, use a compatible checkout, or restore a
known-good backup.

**Migrating legacy data.** Pre-kernel project trees under `projects/` are not
read by the product families directly. Migration scripts live in
`scripts/migrations/v10/` (start with its `MIGRATION.md`); they replay the
legacy tree into the kernel database using only the SDK, with per-phase
dry-runs and receipted idempotency.

The local bridge is optional. If its process or owner lock is unavailable,
keep the local project and use the typed `unavailable` error plus the doctor
report to decide whether to retry. No hosted dependency is needed for the
SDK and CLI journeys.

After creating a project, persist a workspace-local routing preference with
`python3 -m astrid projects select <slug-or-id>`. Confirm it with
`python3 -m astrid projects current --json`; the read-back reports the
canonical project path and whether workspace or user scope supplied the
selection. When `ASTRID_PROJECTS_ROOT` is set, the default workspace preference
is stored inside that root, so separate disposable roots cannot overwrite one
another's selection. Pass `--cwd` to intentionally bind a selection to another
workspace. Project-scoped CLI commands may then omit `--project`, while an
explicit `--project` always takes precedence.

For the complete project, timeline, media, recovery, and failure journeys,
continue with [CLI journeys](guides/cli-journeys.md). For renderer-specific
diagnostics, see [Debugging](guides/debugging.md).

### Canonical timeline schema

The canonical `banodoco_timeline_schema` package is an optional external
dependency. Astrid's default Python install intentionally does not vendor or
declare this private Banodoco workspace package, so clean installs can use the
non-schema surfaces and import Astrid without that checkout. Timeline document
validation, managed rendering/visualization, and the exact canonical-schema
parity assertions require it and fail closed when it is unavailable.

The `dev` extra pins a compatible public source revision so the repository-wide
test suite and CI validate one deterministic schema. This does not add the
schema to Astrid's base runtime dependencies.

Install the package from a compatible Banodoco workspace checkout with the same
interpreter used to run Astrid:

```bash
python -m pip install -e /path/to/banodoco-workspace/packages/timeline-schema/python
python -c "import banodoco_timeline_schema; print('timeline schema available')"
```

The Astrid checkout does not contain `packages/timeline-schema/python`; replace
the placeholder with the path to the external workspace. If the package is not
installed, the timeline parity module remains collectible and skips only its
parameterized canonical-schema checks; its independent compositor checks still
run.

### First visible timeline render

When hand-authoring a timeline, start with root `clips`, a `visual` track,
structured text marked explicitly as `clipType: "text"`, and an MP4 output:

```json
{"tracks":[{"id":"cards","kind":"visual","label":"Cards"}],
 "clips":[{"id":"title","at":0,"track":"cards","clipType":"text","hold":2,
   "text":{"content":"HELLO ASTRID","fontSize":64,"color":"#ffffff","align":"center"}}],
 "output":{"resolution":"640x360","fps":30,"file":"title.mp4"}}
```

The renderer rejects a structured `text` clip without `clipType: "text"` and
checks the default `.mp4` output suffix before starting a render, so these
mistakes do not consume a failed attempt.

## Where to Go Next

- **SDK tutorial** — Walk through the full discover → inspect → invoke →
  read-events loop: [Build Your First Agentic UX](guides/build-your-first-agentic-ux.md).
- **Pack authoring** — Build your own executors, orchestrators, and
  elements: start with [Pack Documentation](packs/) and
  [Creating Packs](packs/creating-packs.md).
- **Contracts index** — Normative contracts that define the SDK surface,
  CLI behavior, error model, output format, and run ledger:
  [Contracts Index](contracts/README.md).
- **Full SDK reference** — DTO catalog and exception hierarchy:
  [SDK Reference](reference/sdk.md).
- **Discovery for agents** — How AI agents consume the capability
  registry: [Discovery for Agents](guides/discovery-for-agents.md).
