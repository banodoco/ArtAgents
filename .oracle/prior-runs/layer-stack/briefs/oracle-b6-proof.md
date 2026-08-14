# Oracle Batch 6 — adversarial honesty of the real stacked render

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Commit: c87cc49f. Read-only. Do not edit. Cite file:line. <400 words.

The claim: `test_real_stacked_render_constructed_plan_threejs_over_remotion` runs REAL threejs ProRes + REAL remotion + REAL ffmpeg-compositor through the public service, 24-frame h264/aac, pixel proof of text-over-media, sidecar planner = `rendering.layer-stack`.

Be adversarial. "Constructed plan" + `_InjectPlanTransport` may be a cheat. Take a position.

Read:
- `tests/core/rendering/test_layer_stack.py` — the real stacked test, `_InjectPlanTransport`, `_assert_stacked_output`, any helpers that build the plan / timeline
- How `RenderService` is constructed and invoked in that test
- `astrid/core/rendering/service.py` only as needed to see what the transport injection skips (planner resolve, plan validate, support)
- Pixel helper(s) used by `_assert_stacked_output`

Do not run pytest.

## Do this

1. REAL BACKENDS. Quote how threejs and remotion are invoked.
   - Are their `render()` implementations called, or are artifacts pre-baked / monkeypatched / stubbed?
   - Is ffmpeg-compositor's real `finalize()` called (filtergraph overlay), or a fake merge?
   - Any `@patch` / MagicMock / pre-written .mov/.mp4 fed in as layer artifacts?

2. INJECT TRANSPORT. Quote `_InjectPlanTransport` in full (or the essential methods).
   - What does it replace (planner? support? validate? resolve?)?
   - Does the injected `RenderPlan` still go through `RenderPlan.__post_init__` (overlap/gap/z rules)?
   - Does the service still stamp `metadata.astrid_layer` for z>0, still slice tracks, still run real backends + compositor?
   - Would this plan be *emitted* by `rendering.layer-stack` if remotion is in the registry? (Host says they swapped z because remotion would fast-path.) If the planner would never emit this assignment, say so plainly.

3. PIXEL PROOF. Quote `_assert_stacked_output` (and callees) when `proof=True`.
   - What pixels are sampled (coords, which frames)?
   - Does it prove TOP painted (text color present) AND BOTTOM visible around the text (media color in a region the text does not cover)?
   - Could a solid overlay, a concat of remotion-only, or a black/transparent fail still pass?
   - Is this the same helper used by compositor synthetic tests, or a weaker check?

4. SIDECAR / CONTAINER. What is asserted on ffprobe (codec, pix_fmt, frames, audio) and provenance (planner id, finalizer id)?

5. HONESTY VERDICT. One of:
   - REAL: public service, real backends, real compositor, plan is a valid LayerRef stack, pixel proof distinguishes text-over-media
   - PARTIAL: real render path but planner-bypassed / proof too weak / assignment planner would never emit
   - FAKE: mocks, pre-baked artifacts, or proof that cannot fail

## Report shape

```
BACKENDS: real|mocked — threejs= remotion= compositor= patches=
INJECT: skips= post_init= stamp= slice= planner-would-emit?
PROOF: samples= top-painted= bottom-visible-around= false-pass?
SIDECAR: ffprobe= planner= finalizer=
HONESTY: REAL|PARTIAL|FAKE — one sentence
BLOCKER?: none | numbered (only if the test does not prove a real 2-layer render)
```
