# Foley Review Executor

Use `foley.foley_review` after Foley generation to eyeball each tile clip
paired with its generated audio. Output is a single static `review.html` that
can be opened directly in a browser. Each tile has thumbs-up / thumbs-down
buttons; pressing a button writes a per-tile flag to `flagged.json` next to
`review.html` (via a tiny `download` step — no server required).

Inspect first:

```python
import astrid.sdk as sdk
cap = sdk.get_capability("foley.foley_review")
```

Run:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "foley.foley_review",
        kind="executor", project="demo",
    inputs={"manifest": "runs/foley_map/example/tiles.json"},
)
```

Open `runs/foley_map/example/review.html` in your browser. Audio paths in the
manifest are resolved relative to the manifest file's parent directory.
