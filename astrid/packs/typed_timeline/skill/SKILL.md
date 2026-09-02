---
name: typed_timeline
description: >
  Map admitted typed rows into validated runtime render timelines using
  explicit mapping resources.
---

# Typed Timeline

`typed_timeline.map` is a capability adapter for turning an admitted row
contract into a validated timeline JSON artifact. It does not open a database,
create a writer, or claim ownership of the runtime timeline. The runtime-owned
run supplies the input boundary and owns the resulting artifact.

## Entrypoint

Invoke the executor through the SDK with an explicit source and mapping:

```python
import astrid.sdk as sdk

result = sdk.invoke("typed_timeline.map", inputs={
    "source": "runaway",
    "mapping": "runaway_colour",
    "run_id": "RUN_01ABC",
})
```

`source` accepts the admitted `runaway` row contract or JSON rows. Mapping
resources are `runaway_colour` and `runaway_text`; they are pure mapping
configuration, not a local Runaway store. The executor validates ordinals,
durations, prompts, metadata, and mapping names before producing output.

## Boundary

Keep Runaway rows, task/run identity, receipts, and durable resource custody in
the workspace runtime. Do not add migrations, repositories, schema packs, SQL,
or a local bridge under this pack. Timeline rendering and visualization remain
runtime-backed rendering capabilities.
