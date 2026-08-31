# Iteration Video

Reads the selected runtime project's runs through the generated client, then
chains `iteration.assemble` and `rendering.render` to create an iteration recap.
The retired `iteration.prepare` executor and thread/variant sidecars are not
declared, invoked, or consulted.

The render handoff is explicit: assemble writes `hype.timeline.json` and `hype.assets.json`, then `rendering.render` consumes those exact files and publishes `iteration.mp4` plus `iteration.mp4.provenance.json` directly alongside the canonical iteration metadata.

Inspect first when provenance quality is uncertain (internal runner command;
not a public entrypoint):

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.video_editing.orchestrators.iteration_video.run inspect @active --no-content
```

Run through the SDK. The pack-level `--thread` is an optional lineage selector
matched against runtime run metadata; it is not a generic Astrid session
binding flag.

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.iteration_video",
        kind="orchestrator", project="demo",
    inputs={"thread": "@active"},
)
```

V1 supports chaptered mode only. `--direction` is a label, `--renderers` and `--clip-mode` are recorded as requested planning hints, and no generated music is created.
