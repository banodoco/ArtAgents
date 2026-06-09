Commands below use example/placeholder ids — after scaffolding, substitute your own capability id.

# Example Orchestrator

Use `video_editing.hype` when a workflow needs to coordinate multiple existing
executors or orchestrators.

Inspect first:

```bash
python3 -m astrid orchestrators inspect video_editing.hype --json
```

Dry-run:

```bash
python3 -m astrid orchestrators run video_editing.hype --dry-run
```

Run:

```bash
python3 -m astrid orchestrators run video_editing.hype
```
