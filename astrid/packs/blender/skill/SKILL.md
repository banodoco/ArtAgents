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

# Local: runs Blender and ffmpeg on this machine.
result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "local",
    "resolution": "1280x720",
    "frames": 1,
})

# Cloud: POSTs to a Blender render API host.
result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "cloud",
    "cloud_url": "http://<render-host>:8778",
    "cloud_token": "<optional-bearer-token>",
})
```

## Scene and settings inputs

- `scene`: declarative scene-spec JSON file. When neither `scene` nor `blend`
  is supplied, the executor uses its built-in pleasant default scene.
- `blend`: existing `.blend` file. It is mutually exclusive with `scene` and
  is rendered as supplied.
- `engine`: `cycles` (default), `eevee`, or `workbench`.
- `device`: `cpu` (default) or `gpu` for Cycles.
- `samples`: Cycles samples; default `64`.
- `resolution`: `WxH`; default `1280x720`.
- `frames`: `1` produces `render.png`; a value greater than `1` produces
  `render.mp4`. Default `1`.
- `fps`: animation frame rate; default `24`.
- `denoise`: enable Cycles denoising when the Blender build supports OIDN.

A named `preset` from `astrid.packs.blender.renders` overrides `scene` and
`blend`. Presets may use `mesh_url` for a direct `.glb`, `.gltf`, `.fbx`, or
archive download, or `sketchfab_uid` for Sketchfab API resolution. The
`head_yaw_deg` and `body_yaw_deg` inputs tune the `wink_turn` preset.

## Execution requirements

Local execution needs `blender` and `ffmpeg` on `PATH`, or a custom Blender
binary in `blender`. Cloud execution needs `cloud_url`; `cloud_token` is sent as
a Bearer token when supplied, and `cloud_timeout` defaults to 1800 seconds.
The local path runs Blender in a temporary working directory and copies the
final artifact into the managed output. Cloud responses are classified from the
response content type/output headers.

A preset is an animation path: if `frames` is omitted or `1`, the runtime uses
60 frames. A failed executable, invalid scene file, missing cloud URL, failed
host request, or failed ffmpeg encode is a typed execution error with recovery
guidance; it is not silently switched between local and cloud execution.

## Outputs and owned resources

For `out="./out"`, the declared outputs are:

- `./out/render/render.png` for a still, or `./out/render/render.mp4` for an
  animation;
- `./out/manifest.json`, containing executor, execution mode, engine, frame
  count, output type, timing, and cloud provenance when applicable.

The pack-relative implementation resources are the `blender.render`
`executor.yaml`, its `run.py`, `render_core.py`, and the preset builders under
`renders/`. Keep scene inputs and generated outputs outside the pack directory;
the executor owns the output directory passed through `out`.

## Host deployment

The stdlib render server and shared render-core script can run on a host
without an Astrid installation. Provisioning is an operational concern, not a
second rendering entrypoint:

```bash
python -m astrid.packs.blender.deploy hetzner --token "$(cat ~/.astrid/blender-render-token)"
python -m astrid.packs.blender.deploy ssh --host <host> --user <user>
python -m astrid.packs.blender.deploy runpod --gpu "NVIDIA GeForce RTX 4090"
```

Use `runpod-render` for the one-shot launch/install/render/teardown workflow and
`teardown-runpod --pod-id <id>` for an explicitly retained pod. Keep the
render-host URL and credentials in deployment configuration; do not put them
in scene JSON.

## Do not use this pack for

- canonical timeline rendering or timeline visualization;
- media import, editing, or compositing;
- a cloud fallback when local Blender is unavailable.
