# Renders — the Blender scratchpad

This package holds **specific, creative renders** that leverage the Blender core
engine (`astrid/packs/blender/render_core.py`) without living inside it.

**Core = reusable machinery** (scene builder, render server, executor, deploy,
mesh fetch). **`renders/` = disposable, per-shot scenes.** Keeping them separate
means you can iterate on a render (or throw one away) without touching the
engine, and anyone can drop in a new render without understanding the core.

## Add a render

1. Create `<name>.py` here (e.g. `product_spin.py`).
2. Define `build(settings: dict) -> str` that returns a **self-contained** Blender
   Python script (it runs inside `blender -b -P …`, stdlib + `bpy`/`mathutils`
   only — no Astrid imports at runtime).
3. Use the placeholders `__MESH_FILE__` and `__OUTPUT__` for the mesh path and
   output directory; the render runner fills them. Use `__SETTINGS__` only if you
   want the runner to embed a normalized settings dict (otherwise embed your own
   constants). `build()` runs **client-side** so it MAY import Astrid helpers
   (e.g. `render_core.normalize_settings`) to compute the script.

That's it — it's auto-discovered by name.

Template:

```python
from astrid.packs.blender.render_core import normalize_settings

_TEMPLATE = '''\
import bpy, os
SETTINGS = __SETTINGS__
OUTPUT = __OUTPUT__
MESH_FILE = __MESH_FILE__

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if MESH_FILE:
        bpy.ops.import_scene.gltf(filepath=MESH_FILE)
    # ... build your scene, keyframes, camera ...
    bpy.context.scene.render.filepath = os.path.join(OUTPUT, "frame_")
    bpy.ops.render.render(animation=True, write_still=True)

if __name__ == "__main__":
    build()
'''

def build(settings):
    s = normalize_settings(settings)
    return _TEMPLATE.replace("__SETTINGS__", repr(s))
```

## Run a render

```python
import astrid.sdk as sdk

# Via the Astrid executor (cloud host):
result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "cloud",
    "cloud_url": "http://<host>:8778",
    "cloud_token": "<tok>",
    "preset": "wink_turn",
    "sketchfab_uid": "<uid>",
    "frames": "60",
})

# Or directly (bypassing the executor), see deploy.render_via_http.
```

Mesh sources for presets: a direct `--mesh-url` (e.g. a Khronos sample
`.glb`), or `--sketchfab-uid` (resolved to a download URL via the token at
`~/.astrid/sketchfab-token`; see `mesh_fetch.py`).

## Existing renders

- **`wink_turn`** — a rigged character seen from behind; only its head turns to
  look back (like someone called its name), it winks (eye-blink shape key), and
  the camera dollies to a head close-up. Arms held by its sides. Works best with
  a face-rigged model (e.g. Sketchfab "Rigged T-Pose Human Male w 50 Face
  Blendshapes").
