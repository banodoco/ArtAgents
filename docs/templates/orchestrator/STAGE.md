# Example Orchestrator

Use `builtin.example_orchestrator` when a workflow needs to coordinate multiple existing
executors or orchestrators.

Inspect first:

```bash
python3 -m astrid orchestrators inspect builtin.example_orchestrator --json
```

Dry-run:

```bash
python3 -m astrid orchestrators run builtin.example_orchestrator --dry-run -- --dry-run
```

Run:

```bash
python3 -m astrid orchestrators run builtin.example_orchestrator -- --dry-run
```
