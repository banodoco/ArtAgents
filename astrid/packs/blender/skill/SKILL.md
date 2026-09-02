---
name: blender
description: >
  Render standalone Blender scenes or .blend files to still images or
  animations locally or through a remote Blender render host.
---

# Blender

The Blender pack owns standalone 3D-scene rendering. Use it for a scene spec or
an existing `.blend` file; use the `rendering` pack for Astrid timeline/video
renders.

## Entrypoint

The pack exposes one executor: `blender.render`. The executor requires
`execution` to be either `local` or `cloud` and writes its results below the
requested output directory.

```python
import astrid.sdk as sdk

result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "local",
    "resolution": "1280x720",
    "frames": 1,
})
```

## Scene and settings inputs

- `scene`: declarative scene-spec JSON; when omitted, the executor uses its
  built-in default scene.
- `blend`: existing `.blend` file, mutually exclusive with `scene`.
- `engine`: `cycles` (default), `eevee`, or `workbench`.
- `device`: `cpu` (default) or `gpu` for Cycles.
- `samples`, `resolution`, `frames`, `fps`, and `denoise` control rendering.
- A named preset from `astrid.packs.blender.renders` overrides `scene` and
  `blend` and may resolve a direct mesh URL or Sketchfab asset.

## Ownership and execution

Local execution needs Blender and ffmpeg on `PATH`; cloud execution needs an
explicit `cloud_url` and optional bearer token. Failed executables, invalid
inputs, host errors, and encoding failures are typed execution errors. The
pack does not silently switch execution modes or write generated outputs into
the source pack. Keep scene inputs and outputs in the caller's project/run
boundary.

Use this pack only for standalone Blender scenes. Canonical timeline rendering,
media import/editing, and cloud fallback policy belong to their respective
runtime-backed packs.
