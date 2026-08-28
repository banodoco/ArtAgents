# Exploration brief E2 — routing + direct-invocation reality

READ-ONLY exploration (no file modifications). One of several parallel explorers. Goal: verified facts with file/line evidence, ranked findings, <300 words.

Context: megado run adding text-clip support to `rendering.ffmpeg`. Planner non-goal: no `legacy_hybrid` changes. Known: `legacy_hybrid` defaults — simple `(rendering.ffmpeg, rendering.remotion)`, complex `(rendering.remotion,)`; text clips land in complex windows → Remotion. We must confirm the deployment reality and that the ffmpeg backend is directly invocable.

Questions:
1. Does ANY production/pack config in the repo set `backend_config` keys `legacy_hybrid.simple_renderers`, `complex_renderers`, or `renderers` (search yaml/json/toml/py, exclude tests/)? Where would backend_config come from at runtime (`RenderRequest.backend_config` producers)?
2. Which planner does `astrid render` (or the render executor) use by default for a media+text timeline — `legacy_hybrid` or `layer_stack`? Trace the actual selection code (pack wiring/entry points) and cite file/line.
3. Direct invocation: confirm how `rendering.ffmpeg` is invoked as a backend process — `renderer.yaml` command (`python3 run.py`), operations `render`/`support`, request/response protocol in `run.py` (`_protocol_render`, `main`). What exactly does a caller pass (stdin JSON? file paths?) — cite the protocol shape.
4. Is there any existing caller in the repo that invokes `rendering.ffmpeg` directly (not via legacy_hybrid)? E.g. tests, cut pipeline, finalize path.

Report file/line evidence for each answer. Note explicitly anything that contradicts the assumptions above.
