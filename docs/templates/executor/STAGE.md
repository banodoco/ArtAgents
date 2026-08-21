Commands below use example/placeholder ids — after scaffolding, substitute your own capability id.

# Example Executor

Use `editorial.arrange` when one concrete input artifact should be converted into
one result artifact.

Inspect first:

```python
import astrid.sdk as sdk

cap = sdk.get_capability("editorial.arrange")
```

Dry-run:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "editorial.arrange",
    inputs={"input": "path/to/input.json"},
    out="runs/example",
    dry_run=True,
)
```

Run:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "editorial.arrange",
    inputs={"input": "path/to/input.json"},
    out="runs/example",
)
```
