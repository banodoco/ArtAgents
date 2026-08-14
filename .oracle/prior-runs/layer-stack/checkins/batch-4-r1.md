I'll verify commit `70c5cdee` against the four ProRes 4444 mandates as oracle, not implementer. First I'm loading the megado skill and the landed diff.I'm the oracle, not the implementer. Next I'll inspect the worktree and dispatch Flash to verify the four mandates against `70c5cdee`.Previous Batch 4 check-in and the rework brief are next — I'll use those to write Flash verification briefs.Commit scope is tight. I'll write the Flash briefs and pull the OMP flags plus the critical remotion/shared/service paths.Writing three Flash briefs and launching them in parallel while I review the critical paths myself.Flash is running. I'll read remotion flags, theme neutralization, service path-binding, and the tests in parallel.Facts and path-binding Flash reports are in. I'll read those while the critique pass finishes.Flash critique is PASS and matches my read. Writing the check-in, then the verdict.**PASS.** Batch 5 may start.

Delegated Flash facts + path-bind + critique (`.oracle/findings/oracle-b4r-{facts,paths,critique}.txt`). Host re-checked the cited lines. Full check-in: `.oracle/checkins/batch-4-r2.md`.

All four mandates landed on `70c5cdee`. Scope is clean: no `service` / dispatch / `validate_output_name` / compositor / concat. (`.oracle/checkins/batch-4.md` was rewritten — ledger only.)

1. **Flags/profile.** Stamp → `--image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444`. Declared = probed: mov / prores / `yuva444p12le` / `1/90000` / `pcm_s16le`. Unstamped: no extra flags, h264/yuv420p/.mp4.
2. **Theme.** `theme_color["bg"] = "transparent"` on the per-run props copy. DOM `TimelineComposition.tsx:272` is raw CSS `backgroundColor` — `transparent` is valid. Threejs `<color>` skip unchanged (`:432`).
3. **Naming.** Backend remaps `.mp4`→`.mov`. Service still asks for `segment-NNNN.mp4`. Compositor/concat read `artifact.path` (`compositor/run.py:541`); no basename==`output_name` check. Path-bind is consistent.
4. **Tests.** `.mov`/prores/`yuva444p12le`; `_threejs_direct_request` is a `RenderRequest`; `corner[3] == 0` from ffmpeg RGBA frame 0 (real pixel). Unstamped corner stays alpha 255. Mocked flag/theme test re-ran: 1 passed.

`_timeline_alpha` / `_alpha_output_name` are reusable pack helpers. `_shared` already imported `astrid.core`; no new leak.

**Batch 5:** remotion/threejs stamped tops emit ProRes 4444 `.mov` with a real alpha plane. **vp9 is not alpha.** Fast-path remotion-only still concat. Do not feed a canonical h264 `request.profile` into stamped remotion/threejs `support()` — they produce ProRes, not the plan mp4.
