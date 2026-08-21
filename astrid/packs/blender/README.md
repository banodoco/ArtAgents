# Astrid Blender pack

Render 3D scenes with Blender, **locally** or on a **remote cloud render host** —
either the always-on Hetzner box (CPU) or an on-demand **RunPod GPU pod**. The
executor works the same way in both modes; only the transport differs.

## Pieces

```
astrid/packs/blender/
  render_core.py                    # stdlib-only scene→Blender-script builder (shared)
  executors/render/
    executor.yaml                   # blender.render executor declaration
    run.py                          # executor: --execution local|cloud
  server/
    blender_render_server.py        # stdlib HTTP render API (deployed to a host)
    blender-render-api.service      # systemd unit
  deploy.py                         # provision/deploy hosts: hetzner | ssh | runpod | runpod-render
```

The render server and `render_core.py` are dependency-free (stdlib only) so they
run on a host **without an Astrid install** — `deploy.py` copies them over.

## Run a render (the Astrid executor)

```python
import astrid.sdk as sdk

# LOCAL — runs blender on this machine
result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "local",
    "samples": "64",
    "resolution": "1280x720",
})

# CLOUD — POSTs to any host running the render API (Hetzner box, a RunPod pod, …)
result = sdk.invoke("blender.render", out="./out", inputs={
    "execution": "cloud",
    "cloud_url": "http://<host>:8778",
    "cloud_token": "<token>",
})
```

Inputs: `scene` (declarative spec JSON; a pleasant default scene is used if
omitted) or `blend` (an existing `.blend` file). `frames=1` → still PNG;
`frames=N>1` → mp4 animation. See `executor.yaml` for the full list.

## Provision a render host

```bash
# Hetzner box (always-on, CPU). Installed live — no reset.
python -m astrid.packs.blender.deploy hetzner --token "$(cat ~/.astrid/blender-render-token)"

# Any SSH host
python -m astrid.packs.blender.deploy ssh --host 1.2.3.4 --user root

# RunPod: persistent GPU pod (keep up, tear down manually)
python -m astrid.packs.blender.deploy runpod --gpu "NVIDIA GeForce RTX 4090"

# RunPod: one-shot ephemeral GPU render (launch → install → render → teardown)
python -m astrid.packs.blender.deploy runpod-render \
  --out ./render.png --device gpu --teardown auto

python -m astrid.packs.blender.deploy teardown-runpod --pod-id <id>
```

### Notes

- **Hetzner box:** 159.69.51.216, render API on `:8778` behind a Hetzner Cloud
  Firewall (only 22/8080 open). Reach it via an SSH tunnel:
  `ssh -fN -L 18778:127.0.0.1:8778 root@159.69.51.216`, then
  `cloud_url=http://127.0.0.1:18778`. No hcloud token is on the machine, so the
  cloud firewall can't be opened programmatically — use the console if you need a
  public URL. The Arnold docker container on :8080 is separate; don't touch it.
- **RunPod:** no official Blender image exists, so a CUDA image
  (`runpod/pytorch:…cuda…`) is launched and the **official** GPU-capable Blender
  tarball is installed (the distro `apt` Blender has no CUDA). API key is read
  from `~/.runpod/config.toml`; the `runpod-lifecycle` package drives the pod
  lifecycle. Pod SSH uses `~/.ssh/id_ed25519`.
- **Teardown:** `runpod-render --teardown auto` (default) tears the pod down the
  moment the render finishes; `--teardown never` keeps it up; `--keep-after-seconds N`
  lingers N seconds first.
- **GPU vs CPU:** the Hetzner box has no GPU (CPU/Cycles only). RunPod gives a
  10–50× Cycles speedup and enables EEVEE. First GPU render compiles CUDA/OptiX
  kernels (one-time overhead); complex scenes benefit most.

## Scene spec

A declarative JSON scene (see `render_core.DEFAULT_SCENE`): objects (cube, sphere,
monkey, plane, …), lights (sun/area/point/spot), camera, background, optional
spin animation. Example:

```json
{
  "background": "#161823",
  "objects": [
    {"type": "monkey", "location": [0, 0, 1], "color": "#5bc0de", "animate": "spin"}
  ],
  "lights": [{"type": "area", "location": [4, -4, 6], "energy": 1200}],
  "camera": {"location": [6, -6, 4.5], "rotation_deg": [66, 0, 45]}
}
```
