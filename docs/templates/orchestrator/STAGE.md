Commands below use example/placeholder ids — after scaffolding, substitute your own capability id.

# Example Orchestrator

Use `video_editing.hype` when a workflow needs to coordinate multiple existing
executors or orchestrators.

Inspect first:

```python
import astrid.sdk as sdk

cap = sdk.get_capability("video_editing.hype")
```

Dry-run:

```python
import astrid.sdk as sdk

result = sdk.invoke("video_editing.hype", dry_run=True)
```

Run:

```python
import astrid.sdk as sdk

result = sdk.invoke("video_editing.hype")
```
