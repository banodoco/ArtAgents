# Example Executor

Use `builtin.example_executor` when one concrete input artifact should be converted into
one result artifact.

Inspect first:

```bash
python3 -m astrid executors inspect builtin.example_executor --json
```

Dry-run:

```bash
python3 -m astrid executors run builtin.example_executor --input input=path/to/input.json --out runs/example --dry-run
```

Run:

```bash
python3 -m astrid executors run builtin.example_executor --input input=path/to/input.json --out runs/example
```
