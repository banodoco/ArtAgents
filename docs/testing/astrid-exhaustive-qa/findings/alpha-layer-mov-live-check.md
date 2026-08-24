# Alpha-layer MOV live check

Date: 2026-08-24 (Europe/Berlin)  
Surface: public documented `astrid.sdk.rendering.render`, project
`sdk.invoke_result("rendering.render")`, canonical `astrid timelines render`,
then focused regression guards  
Verdict: **FIXED end to end — stamped alpha layers publish durable truthful
MOV; ordinary output remains MP4; invalid MOV requests fail before admission.**

## Contract and live failure

The active public layer-stack contract in
`docs/reference/layer-stack.md` explicitly says that `z > 0` layers carry
`astrid_layer.alpha: true` and emit transparent ProRes 4444 in `.mov`, while
`z = 0`/unstamped output remains opaque H.264/AAC `.mp4`. This is not a retired
VP9 or legacy task-mode expectation.

On the disposable public SDK fixture `/tmp/astrid-alpha-live-check`, a minimal
text timeline with the documented stamp:

```json
"metadata": {"astrid_layer": {"z": 1, "alpha": true}}
```

was rendered through:

```python
from astrid.sdk.rendering import render
render(
    timeline_path="stamped-alpha.timeline.json",
    assets_registry_path="assets.json",
    out_path="stamped-alpha.mov",
    backend="rendering.remotion",
)
```

Before the correction, this failed at the public service boundary with:
`RendererProtocolError: output_name must end in .mp4 for the selected render
profile; got 'stamped-alpha.mov'`. Remotion never ran. The same unstamped
timeline to `.mp4` succeeded, confirming the defect was the service's
filename admission predicate, not the backend or alpha codec path.

## Smallest correction

One shared core output policy is now used by direct `RenderService`, project
SDK preflight, canonical timeline preflight, and the executor's basename
guard. It permits `.mov` only when all of the following are true:

1. the requested name ends in `.mov`;
2. the input timeline has the exact `metadata.astrid_layer.alpha == true`
   stamp.
3. no explicit profile was supplied, or the explicit profile describes the
   truthful MOV/ProRes/`yuva444p12le`, 90 kHz time base, and PCM S16LE 48 kHz
   stereo mux.

Malformed/unreadable timelines and ordinary un-stamped `.mov` requests still
fail closed. The executor now validates only portable basename safety, so it
cannot override the service's media-aware decision. The alpha backend mux
profile always declares the PCM audio it actually produces instead of
inheriting an opaque AAC request.

## Post-fix live proof

The same public SDK workflow now succeeds:

- stamped output: `/tmp/astrid-alpha-live-check/stamped-alpha-fixed2.mov`
- `ffprobe`: `prores`, `yuva444p12le`, 320×180, `1/90000`, PCM S16LE;
  duration 0.500s
- first decoded RGBA corner: `[0, 0, 0, 0]`
- provenance engine: `rendering.remotion`, SHA-256 matches the artifact

The same public workflow with no alpha stamp succeeds to
`opaque-fixed2.mp4`:

- `ffprobe`: H.264, `yuvj420p`, AAC, 320×180; duration 0.555s
- first decoded RGBA corner: `[0, 0, 0, 255]`
- provenance engine: `rendering.remotion`, SHA-256 matches the artifact

Focused real-service guard:

```text
pytest -q \
  tests/packs/rendering/test_remotion_backend.py::test_stamped_top_layer_via_real_service_is_mov_prores_with_alpha
1 passed in 37.45s
```

The guard covers both stamped `.mov`/ProRes/transparent-alpha and unstamped
`.mp4`/H.264/opaque behavior.

### Managed/canonical replay

Fresh root: `/private/tmp/astrid-alpha-managed-fix.YLb6Pe`.

The version-pinned product command:

```bash
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-alpha-managed-fix.YLb6Pe \
python3 -m astrid timelines render alpha-layer \
  --project alpha-lab --expected-version 1 \
  --backend rendering.remotion --output-name canonical-alpha.mov --json
```

succeeded as kernel run `5c7d0ddc5dd5f804933ee6b84c`. Its primary media
is managed object
`87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44`;
`media show` reports `video`, `video/quicktime`, container `mov`, and
`rel_path: out/canonical-alpha.mov`. `ffprobe` reports ProRes profile 4444,
tag `ap4h`, `yuva444p12le`, 320×180, 30 fps, `1/90000`, plus PCM S16LE 48 kHz
stereo. The decoded RGBA alpha extrema are `0..255`, with corner
`(0,0,0,0)` and 11,477 nonzero-alpha pixels.

The durable provenance declares the same media digest and MOV profile, and
stamps canonical timeline `e5b84ea4-b110-5d95-9c26-1a0f8700dfa4`, version 1,
event `fe4a66963e844283be1608db73bcdf00`, head hash
`e8aba446a706d1307e8dd7aa37b1cb3537741e53f37e650a54b241e442bb2554`,
config hash `00e25f668910db050ab35ab782ca17c9325edffee90e9b790eab5453f2a95197`,
and registry hash
`917c9dd6b3827ebd1df91cc3f8dad532f64102cafd796a2ff59b41f2c0630d30`.

The same materialized timeline also succeeded through project
`sdk.invoke_result("rendering.render")` as run
`e000840a0a1eb7a14356ae97f9`, proving the generic project SDK surface no
longer has an `.mp4`-only override.

An unstamped canonical `.mov` returned `validation_error` with every run,
task, and attempt ID null; `runs list` remained empty. After the positive
controls existed, an alpha `.mov` with an explicit H.264/yuv420p/AAC profile
also returned `validation_error` with null IDs and the exact codec, pixel
format, and audio mismatches; run count stayed unchanged. The opaque canonical
MP4 control succeeded as run `2d2b7808e6a56a2b82fc636d06`, probing as
H.264/AAC with alpha fixed at `255..255`.

Focused validation after the integration correction:

```text
144 passed in 91.33s
```
