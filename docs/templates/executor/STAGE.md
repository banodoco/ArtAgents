Commands below use example/placeholder ids — after scaffolding, substitute your own capability id.

# Example Executor

Use `editorial.arrange` when one concrete input artifact should be converted into
one result artifact.

Inspect first:

```bash
python3 -m astrid executors inspect editorial.arrange --json
```

Dry-run:

```bash
python3 -m astrid executors run editorial.arrange --input input=path/to/input.json --out runs/example --dry-run
```

Run:

```bash
python3 -m astrid executors run editorial.arrange --input input=path/to/input.json --out runs/example
```
