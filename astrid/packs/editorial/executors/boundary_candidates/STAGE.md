# Boundary Candidates Executor

Use `editorial.boundary_candidates` to package likely start/end frame candidates
for visual review after transcript, scene, shot, or quality-zone analysis.

## Run

Run it through the SDK; each executor input maps 1:1 to an `inputs` entry:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.boundary_candidates",
        kind="executor", project="demo",
    inputs={
        "video": "source.mp4",
        "manifest": "runs/boundary-review/boundary_manifest.json",
    },
)
```

The manifest must contain a `talks` array. Each talk should provide enough
timing data for candidate windows, for example start/end seconds plus a label or
title. Keep the window smaller than very short source clips; the default window
is designed for real talk footage and can extend candidates beyond tiny test
fixtures.

Useful optional inputs supported by the underlying CLI include `asset_key`,
`transcript`, `scenes`, `shots`, `quality_zones`, `holding_screens`, `kind`,
`window`, and `max_candidates`.
