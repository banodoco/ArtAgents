# Replay 3: managed/canonical alpha MOV

Date: 2026-08-24 (Europe/Berlin)  
Surface: public CLI, documented public SDK, public media/run readback, and
ffprobe/ffmpeg artifact inspection.  
Method: independent black-box LIVE replay; no source, tests, database edits,
or product edits.  
Disposable root: `/private/tmp/astrid-managed-alpha-replay-fCTz6c`.

## Verdict

**PASS — managed/canonical alpha MOV is coherent end to end.**

On a fresh project, the public version-pinned canonical render produced a
durable ProRes 4444 MOV with `yuva444p12le` and PCM S16LE stereo; an actual
decoded frame contained transparency; durable provenance carried canonical
kernel authority; the raw project SDK route also passed; unstamped MOV and
incompatible explicit alpha profiles failed as typed pre-admission errors
with null IDs/no run rows; and ordinary unstamped MP4 remained opaque
H.264/AAC.

## Fixture and discovery

Created the project through the public gateway:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-managed-alpha-replay-fCTz6c \
python3 -m astrid projects create alpha-lab \
  --name 'Alpha Managed Replay' --json
```

`timelines create --help` exposed the public `--config` JSON route. The alpha
timeline was created at version 1, made default, and contained the exact
documented stamp:

```json
"metadata": {"astrid_layer": {"z": 1, "alpha": true}}
```

Its public config supplied a 320x180/30 fps canvas and one text clip.
`timelines show alpha-layer --project alpha-lab --json` returned the same
stamp, `config_version: 1`, UUID
`5d07e31c-d49a-5d25-aa11-722c5ec395bd`, and ULID
`85fpz2txs0p67qt19q1gqanh98`. Render help was copyable and documented
`--expected-version`, the alpha MOV exception, flat profiles, and the default
theme canvas. No private runner command was needed.

## Pre-admission rejection

Before any render, `runs list --project alpha-lab --json` contained zero rows.

An unstamped request:

```bash
python3 -m astrid timelines render opaque --project alpha-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name invalid-opaque.mov --json
```

returned `ok:false`, `error.code:"validation_error"`, typed
`CapabilityValidationError`, and:

```text
output_name 'invalid-opaque.mov' uses .mov, but the timeline is not stamped metadata.astrid_layer.alpha=true
```

`kernel_run_id`, `kernel_task_id`, `kernel_attempt_id`, and `run_id` were all
null; run count stayed 0.

An explicit, structurally complete MOV profile with H.264/`yuv420p`/AAC
returned another typed validation error:

```text
alpha MOV output has an incompatible explicit render profile:
video_codec='h264' (requires 'prores');
pixel_format='yuv420p' (requires 'yuva444p12le');
audio_codec='aac' (requires 'pcm_s16le')
```

All IDs were null again, and the run count stayed 0 before and after. No
output, provenance, snapshot, or managed media row was created.

## Canonical alpha MOV

```bash
python3 -m astrid timelines render alpha-layer --project alpha-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name canonical-alpha.mov --json
```

Succeeded as run `8782d9c4555162bd786a527f1c`, task
`95f27f4cbef74c520b8a6daaf2`, attempt
`01m0sqfjyknae8v6msw83dc9fj`. The primary managed media was
`01m0sqfs50gf08v8f5jkqqe89a` with SHA-256
`87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44` at:

```text
/private/tmp/astrid-managed-alpha-replay-fCTz6c/.astrid/media/sha256/87/ae/87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44
```

Public `media show` reported `media_kind:"video"` and
`mime_type:"video/quicktime"`. ffprobe on the durable locator reported
ProRes profile 4444/tag `ap4h`, `yuva444p12le`, 320x180, 30/1 fps, time base
1/90000; and PCM S16LE/tag `sowt`, 48000 Hz, stereo. Duration was 1 second.

Decoding one 320x180 frame to RGBA yielded
`alpha_min=0`, `alpha_max=255`, `nonzero_alpha=11477`, `nonfull_alpha=55723`,
and `corner_rgba=(0,0,0,0)`. This is real transparent decoded content, not
just an alpha-capable codec declaration.

The durable provenance sidecar was media
`01m0sqfs55r8544a3xsnbdzvsh`; its `artifact_profiles[0]` declared MOV, ProRes,
`yuva444p12le`, PCM S16LE, 48 kHz stereo, 320x180, 30/1 fps, and the same
artifact SHA-256. Its canonical authority was:

```json
{
  "authority": "kernel",
  "project_slug": "alpha-lab",
  "project_id": "e045b44b-1311-5b97-a987-1f022fcfbc01",
  "timeline_slug": "alpha-layer",
  "timeline_id": "5d07e31c-d49a-5d25-aa11-722c5ec395bd",
  "timeline_ulid": "85fpz2txs0p67qt19q1gqanh98",
  "config_version": 1,
  "head_event_id": "2d9bac24da2a4ec39477a7c65a29c914",
  "head_hash": "7f748f6aee739870ac6d7d9d3d7fd5a323a7e3119f6002e81131b227f23d433d",
  "config_hash": "8d317e8e38f462bf32f8fb199c5c20a7670e350c66c2ccfa1d08432797e31ff1",
  "registry_hash": "917c9dd6b3827ebd1df91cc3f8dad532f64102cafd796a2ff59b41f2c0630d30"
}
```

Independent public `timelines show` and `timelines history` still returned
version 1 and the exact alpha stamp after render. The result and sidecar were
both content-addressed managed media.

## Raw project SDK route

Using the documented JSON-safe SDK boundary with no private imports:

```python
import astrid.sdk as sdk
result = sdk.invoke_result(
    "rendering.render", kind="executor", project="alpha-lab",
    inputs={"timeline_ref": "alpha-layer", "expected_version": 1,
            "backend": "rendering.remotion", "output_name": "sdk-alpha.mov"},
)
print(result.to_dict())
```

returned `ok:true` with run `ee78c0350112a394cf381902fd`, task
`ad1ceb3dfb735cb43d6155a4e7`, attempt `01m0sqh8c6b898y2x3cwfsxz8r`, and the
same primary alpha digest. It published a separate durable provenance
sidecar. The SDK result was directly JSON-serializable with stable `ok`, ID,
`outputs`, and `error` fields.

## Ordinary MP4 control

```bash
python3 -m astrid timelines render opaque --project alpha-lab \
  --expected-version 1 --backend rendering.remotion \
  --output-name opaque-control.mp4 --json
```

Succeeded as run `f52316107f85663a37527eff4e`. ffprobe reported H.264 High /
`yuvj420p` at 30 fps plus AAC-LC 48 kHz stereo. A decoded RGBA frame had
`alpha_min=255`, `alpha_max=255`, and `corner_rgba=(0,0,0,255)`. Ordinary MP4
behavior remains opaque and unchanged.

## Agent UX friction and severity

No P1/P2 behavior was found. `media show` returns a suffixless CAS locator
and no inline probe object, so an agent must follow
`locations[0].locator` and use an external probe to verify codec/alpha facts.
This is safe and inspectable because the result also returns the requested
label and hash, but an inline probe or obvious managed rel-path would make
verification faster. **P3 ergonomics only; no correctness defect.**

## Final matrix

| Journey | Result |
|---|---|
| Stamped canonical MOV, version-pinned | PASS |
| Durable managed artifact/provenance | PASS |
| ProRes 4444 / `yuva444p12le` + PCM | PASS |
| Real transparent decoded pixels | PASS |
| Canonical kernel authority | PASS |
| Raw project `sdk.invoke_result` | PASS |
| Unstamped MOV pre-admission | PASS; null IDs, zero runs |
| Incompatible explicit alpha profile | PASS; null IDs, zero runs |
| Ordinary unstamped MP4 | PASS; opaque H.264/AAC |

