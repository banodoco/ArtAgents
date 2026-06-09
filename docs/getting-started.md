# Getting Started with Astrid

Astrid is a Python SDK and harness toolkit for building and running
agentic UXes — pipelines where agents and humans collaborate to make art.

## Install

```bash
pip install astrid
```

Astrid requires Python 3.11+.  No API keys, network access, or hosted
services are required — everything runs locally.

For a development install from a local checkout:

```bash
cd /path/to/Astrid
pip install -e .
```

## Your First Command

From any shell, run the universal port-of-call:

```bash
python3 -m astrid next
```

`next` always prints exactly one legal action.  On a cold start it tells
you to attach to a project.  Once attached, it guides you through
discovery, execution, and task steps.  Use it as your always-available
compass.

Other useful zero-setup commands:

```bash
python3 -m astrid status          # read-side breadcrumb
python3 -m astrid attach <project>  # bind a session to a project
python3 -m astrid doctor          # health check
python3 -m astrid setup           # configure local environment
```

## Where to Go Next

- **SDK tutorial** — Walk through the full discover → inspect → invoke →
  read-events loop: [Build Your First Agentic UX](build-your-first-agentic-ux.md).
- **Pack authoring** — Build your own executors, orchestrators, and
  elements: start with [Pack Documentation](packs/) and
  [Creating Packs](packs/creating-packs.md).
- **Contracts index** — Normative contracts that define the SDK surface,
  CLI behavior, error model, output format, and run ledger:
  [Contracts Index](contracts.md).
- **Full SDK reference** — DTO catalog and exception hierarchy:
  [SDK Reference](sdk.md).
- **Discovery for agents** — How AI agents consume the capability
  registry: [Discovery for Agents](discovery-for-agents.md).
