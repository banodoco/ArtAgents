# Checkpoint 4 RE-REVIEW — Batch 4 rework (70c5cdee) — PASS

Oracle: Grok 4.6. Delegated Flash facts + paths + critique
(`.oracle/findings/oracle-b4r-{facts,paths,critique}.txt`). Host
re-checked cited lines.

**Batch 5 may start.**

## The 4 mandates

1. **Flags/profile.** `_timeline_alpha` → remotion CLI
   `--image-format=png --pixel-format=yuva444p10le --codec=prores
   --prores-profile=4444` (`remotion/run.py:594–599`). Declared =
   probed: mov / prores / `yuva444p12le` / `1/90000` / `pcm_s16le`
   (`_shared/__init__.py:304–316`). Unstamped: no extra flags,
   h264/yuv420p/.mp4.

2. **Theme bg.** `theme_color["bg"] = "transparent"` on the per-run
   `merged_props` copy (`remotion/run.py:561–562`). DOM
   `TimelineComposition.tsx:272` is raw CSS `backgroundColor` —
   `transparent` is valid. Threejs `<color>` skip unchanged
   (`ThreeTimelineComposition.tsx:432`).

3. **Naming.** `_alpha_output_name` remaps any non-`.mov` → `.mov`
   (`_shared:274–288`) at remotion SDK + protocol and threejs
   protocol. Service still `segment-NNNN.mp4` (`service.py:1362`).
   No `validate_output_name` / dispatch / compositor / concat touch.

4. **Tests.** Stamped expects `.mov`/prores/`yuva444p12le`.
   `_threejs_direct_request` is a `RenderRequest`. Corner test
   un-xfailed: `corner[3] == 0` via ffmpeg RGBA frame 0 (real
   pixel, not just pix_fmt). Unstamped frozen at corner alpha 255.

## Path-bind

No. Compositor/concat read `artifact.path` (`compositor/run.py:541`).
Service never requires basename == `request.output_name`. Declared
`video.path` is the remapped `.mov`. `yuva*` already counts as
alpha (`:345`).

## Shared

`_timeline_alpha` + `_alpha_output_name` are pack-local helpers.
`_shared` already imported `astrid.core`; no new leak.

## Scope

Product files clean. `.oracle/checkins/batch-4.md` rewritten
(ledger only).

## Batch 5

Top-layer remotion/threejs emit ProRes 4444 `.mov` with a real
alpha plane. **vp9 is not alpha.** Fast-path remotion-only still
concat. Do not feed a canonical h264 `request.profile` into
stamped remotion/threejs `support()` — they produce ProRes, not
the plan mp4.
