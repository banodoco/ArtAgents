I'll gate Batch 3 as oracle: read the frozen criteria and delta, then send mechanical verification to GLM 5.3 Flash before judging.I'll match the prior check-in format, then send GLM one combined verification-and-critique brief so the heavy reading stays out of this thread.I'll write the independent review brief, dispatch GLM, and inspect the hang-fix paths myself while it runs.Command.py already matches the hang-fix contract; next I’ll read the overlay tests and check GLM liveness.GLM’s pass matches the code. I’ll record the check-in artifacts and return the binary verdict.PASS

**AC 1–10**
1. PASS — PNG inputs after assets: `-loop 1 -t {end:.6f} -i` (`command.py:450-453`); test slice `test_ffmpeg_text.py:310`.
2. PASS — one `-t` assertion: overlay index 1 + `-t 3.000000` (END 3.0, not duration 2.0) (`test:314-321`); production uses `overlay.end` (`command.py:452`), never `end-at`.
3. PASS — `[spine][ovK]overlay=0:0:...` (`command.py:320-324`); PNG secondary; test pins `[vout][ov0]overlay=0:0:...[vout]` (`test:343-346`).
4. PASS — `enable='between(t,…)'` literal quotes (`command.py:322`); one argv element `";".join(filters)` (`:466`); `count("'")==2` (`test:349-355`).
5. PASS — both fades always, no zero-guard (`command.py:312-315`); `d=0.000000` (`test:358-373`).
6. PASS — `and not inputs.text_overlays` veto (`command.py:282`); `copy_video_input` stays `None`; libx264+`[vout]` with overlays, `copy` without (`test:376-387`).
7. PASS — no `-shortest` in command.py; `assert "-shortest" not in argv` (`test:324-326`).
8. PASS — empty `text_overlays=()` default (`command.py:52`); overlay loops no-op; stream-copy still available (`test:384-387`). Host: 100 passed.
9. PASS — `clipType == "media"` on visual/audio collection in `build_filter_graph` (`:206,217`) and `_asset_input_argv` (`:415,426`); text without `asset` does not add `-i` (`test:390-398`).
10. PASS — delta is `command.py` + `test_ffmpeg_text.py` only; `run.py` / `renderer.yaml` unchanged.

**Hang-fix:** `-loop 1 -t END` per PNG, spine-first, both fades, no `-shortest`/`-framerate`, one filtergraph, literal quotes, media-only assets, veto #2 independent of `run.py`. All PASS.

**North Star:** simplest toolchain ALIGNED (one filtergraph, no extra binaries/branches). Capability-driven ALIGNED (yaml still media-only; auto-route not this checkpoint). Output parity ALIGNED (absolute END, dual alpha fades, `enable` window). Offline ALIGNED (local PNGs). Anti-patterns: routing lies ALIGNED (yaml does not lead); yaml/support lag ALIGNED (neither touched); no speculative layers; no silent copy-with-overlays; no scope creep.

**Issues:** none. GLM review PASS. Nits (duplicated media collectors; overlapping `-t` slices) not fail-worthy.
