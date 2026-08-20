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

Other useful zero-secret commands:

```bash
python3 -m astrid doctor --json   # read-only health check
python3 -m astrid projects list --json
```

`doctor --json` is the first diagnostic on a clean machine. It reports
`schema_versions`, media paths, SQLite quick-check, and foreign-key status
without repairing or rewriting data. A failing `schema_versions` check means
the database is newer or incompatible with this checkout; preserve the
database, use a compatible checkout, or restore a known-good backup.

The local bridge is optional. If its process or owner lock is unavailable,
keep the local project and use the typed `unavailable` error plus the doctor
report to decide whether to retry. No hosted dependency is needed for the
SDK and CLI journeys.

For the complete project, timeline, media, recovery, and failure journeys,
continue with [CLI journeys](guides/cli-journeys.md). For renderer-specific
diagnostics, see [Debugging](guides/debugging.md).

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
