# Agentic UX Example

External example application demonstrating the full Astrid SDK loop:
**discover → inspect → dry-run invoke → read-events**.

This example imports only `astrid` plus Python standard-library modules.
It exercises the public SDK surface against the canonical `editorial.arrange`
executor and prints a deterministic JSON summary to stdout.

## Quick Start

```bash
python examples/agentic_ux/agentic_ux.py \
    --projects-root /tmp/astrid-demo-projects \
    --capability-id editorial.arrange
```

Output is a single JSON object with four top-level keys:

| Key | Description |
|-----|-------------|
| `discovery` | Count of discovered executors, orchestrators, elements, and total capabilities |
| `inspection` | Capability identity, kind, typed inputs, and outputs |
| `invocation` | Dry-run result (always `dry_run: true` in this example) |
| `events` | Event count and kind sequence read from the committed golden fixture |

## CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--projects-root` | Yes | — | Base directory where a temporary project layout is created for event reading |
| `--capability-id` | No | `editorial.arrange` | Qualified capability ID to inspect and dry-run invoke |

## Golden Events Fixture

The `fixtures/golden_events.jsonl` file contains three pre-computed,
hash-chained task events (`run_started`, `step_dispatched`, `run_completed`).
The example copies this fixture into a temporary project run directory so that
`astrid.read_events()` can observe it without a live executor run. The hashes
are deterministic (computed from fixed timestamps) and pass `verify_chain`.

To regenerate the fixture after a schema change, run a known-good executor
invocation and copy the resulting `events.jsonl` from its run directory.
