I'll gate Batch 6 as oracle: first load the megado/oracle and delegation skills, then send GLM 5.3 Flash a critique brief against the rewritten docs and shipped code.I'll write a GLM critique brief and pull the Batch 6 doc plus the shipped ffmpeg backend so I can check claims against code.I'll reuse the Batch 5 review brief as the template, then dispatch GLM to check the rewritten doc against the shipped ffmpeg backend.I have the rewritten doc. Next I’ll write a mechanical GLM review brief and read the shipped routing, filtergraph, and font/shadow code in parallel.Delta is docs-only. I’ll write the GLM review brief, then check routing, stream-copy, and shadow claims against the code myself.I'll write the GLM review brief and launch it, then run the listed pytest commands in parallel.GLM’s independent review is PASS. I’ll spot-check a few of its line citations, stop the docs-only pytest run, and write the check-in.PASS

Independent GLM 5.3 Flash review (223.2s, exit 0) and oracle read of `5fd08a28..a5fc84f8` agree. One-file commit: `docs/ffmpeg-text-extension.md` (+121/−72). `git diff --name-only c6c505af..HEAD -- docs/` is that file only.

**AC 1** PASS — B6 delta is the seed-plan file only.

**AC 2** PASS — every T8 claim is present and matches shipped code:
- Filtergraph in `command.py:179` `build_filter_graph`; no `section` loop in `run.py`.
- One `_parse_fades` (`text.py:155`) shared by `support.py` and `run.py`.
- System Arial/DejaVu TTF, fail-closed; no `load_default()` / fonttools / woff2 / PowerGrotesk.
- Color: `ImageColor` + `rgba()`; shadow `_parse_text_shadow`; `GaussianBlur(radius=shadow.blur / 2)` at `text.py:343`.
- Window wraps `_clip_duration_seconds`; text `from` rejected (`support.py:285-288`).
- Overlay: full-canvas PNG, `overlay=0:0`, `-loop 1 -t END` (`command.py:452`); no `-shortest` / `-t END-AT` in this chain.
- Default `rendering.render`: None → `"remotion"` → `(rendering.ffmpeg, rendering.remotion)` `auto_route=True` (`service.py:167-177`).
- Fallback: raised kinds `unsupported`/`binary_missing` continue; other `RendererException` re-raise; `not report.supported` continues. Listed fail-closes are real support rejections.
- `LegacyRenderRoutingWarning` (`service.py:114`) fires at auto-route index 0 when ffmpeg is picked.
- `hybrid` → `rendering.legacy_hybrid`, unused on the default path; no hybrid/planner/`service.py` in the run delta.
- Stream-copy gated in support (`_whole_media_optimization`) and `build_filter_graph` (`command.py:280-289`); no third `run.py` veto.
- Live smoke: plate `t=0.5`, mid `t=1.5`, post-END `t=2.6`; not the intro storyboard.

**AC 3** PASS — no hybrid-intercepts-text claim; no yaml/support-not-enough claim.

**AC 4** PASS — only `docs/ffmpeg-text-extension.md` under `docs/` from base.

**North Star:** ALIGNED on simplest toolchain, capability-driven routing (no remaining routing lies in this file), output parity, offline defaults, yaml/support agreement, no silent fallback, no scope creep.

**Issues:** none. Nit: protocol render re-queries support inside `build_render_command` rather than “forwarding” `stream_copy_allowed`; still a two-place veto.
