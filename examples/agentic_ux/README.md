# Agentic UX Example

External example application demonstrating the no-side-effect Astrid SDK
preview loop: **discover → inspect → dry-run invoke**.

This example imports only `astrid` plus Python standard-library modules.
It exercises the public SDK surface against the canonical `editorial.arrange`
executor and prints a deterministic JSON summary to stdout.

## Quick Start

```bash
python examples/agentic_ux/agentic_ux.py \
    --capability-id editorial.arrange
```

Output is a single JSON object with four top-level keys:

| Key | Description |
|-----|-------------|
| `discovery` | Count of discovered executors, orchestrators, elements, and total capabilities |
| `inspection` | Capability identity, kind, typed inputs, and outputs |
| `invocation` | Dry-run result (always `dry_run: true` in this example) |

## CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--capability-id` | No | `editorial.arrange` | Qualified capability ID to inspect and dry-run invoke |

## Live runtime work

This example intentionally does not create a local project, database, or event
file. For live execution and event observation, open an explicit
`AstridClient` against the Banodoco workspace runtime and use
`client.invoke_result(...)` and `client.runs.events(project, run_id)`; the
runtime owns admission, execution, ordering, and event storage.
