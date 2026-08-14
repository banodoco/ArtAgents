# Checkpoint 4 — Batch 4 (Layer Stack) — ISSUES

Oracle: Grok 4.6. Delegated Flash facts + critique
(`.oracle/findings/oracle-b4-{facts,critique}.txt`). Web Flash stalled
(0 bytes); host `web_search` used after that failure.

**Do not start Batch 5.**

## ISSUES

**PATH: (a)** Rework `2a2ba6b8` to ProRes 4444 for stamped-alpha segments.
Keep stamp consumption + threejs bg-skip. Reject vp9/webm for alpha.
Do **not** keep the current vp9/yuv420p "honest-opaque" story — B4's
checkpoint is a real alpha plane + corner alpha 0, and compositor
already accepts ProRes yuva for free.

1. **Flags / declared profile.** `_shared/__init__.py:283–295` and
   `remotion/run.py:575–580` still emit
   `--image-format=png --pixel-format=yuva420p --codec=vp9` and declare
   webm/vp9/yuva420p/aac. Host + executor: that mux is **yuv420p, no
   alpha**, audio **opus**. Remotion docs still advertise VP8/VP9+yuva;
   4.0.509 does not emit i**ISSUES — path (a). Do not start Batch 5.**

Delegated: Flash facts + critique (`.oracle/findings/oracle-b4-{facts,critique}.txt`). Web Flash stalled (0 bytes); after that I searched Remotion’s transparent-video docs. Cited lines checked.

**Why (a):** Host-probed ProRes 4444 emits `yuva444p12le`. Compositor change is **zero** for inputs: `yuva*` already counts as alpha (`compositor/run.py:345`); `libvpx-vp9` only if `alpha AND vp9` (`:649–651`); native ProRes decode. Composite **output** stays canonical mp4. Keep `2a2ba6b8` stamp + threejs bg-skip; they are required. Do **not** keep vp9/yuv420p as “honest opaque” — B4’s checkpoint is a real alpha plane.

1. **Rework flags/profile.** Drop `--codec=vp9 --pixel-format=yuva420p`. Use the host-probed combo: `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png`. Declare **probed** mov/prores/`yuva444p12le` + real time_base/audio (not webm 1/1000/opus). Docs still advertise VP8/VP9+yuva; 4.0.509 does not emit it.

2. **Neutralize remotion theme bg.** Threejs skip (`ThreeTimelineComposition.tsx:432`) is correct — **keep**. DOM `TimelineComposition.tsx:272` still paints `theme.visual.color.bg`. Without a transparent theme bg, ProRes corners stay alpha 255. Set `visual.color.bg` transparent in merged_props when stamped (no `node_modules` edit).

3. **Naming.** Compositor already accepts `.mov`/`.webm` artifacts. Remotion rejects `.mp4` with prores. Service hardcodes `segment-NNNN.mp4` (`service.py:1362`); `_OUTPUT_NAME_RE` already allows `.mov`; path binding is containment-only. **B4: remap `.mp4`→`.mov` in the remotion backend when stamped.** Service rename is optional later. Do not touch `validate_output_name` / dispatch.

4. **Tests.** `.mov` (or remapped path); threejs dict→`RenderRequest`; un-xfail `corner[3]==0`; flag test expects prores.

**Batch 5 assume:** remotion + threejs stamped tops are ProRes 4444 `.mov` with a real alpha plane. Opaque stacking unchanged. vp9/webm is not an alpha format. Fast-path remotion-only still concat. Full check-in: `.oracle/checkins/batch-4.md`.
 neutralization). Opaque
stacking unchanged. vp9/webm is not an alpha segment format.
Fast-path remotion-only still concat. Planner does not need to
restrict top-layer engines to ffmpeg.

**Constraint revision:** "VP9/yuva at `segment-NNNN.mp4`" is dead
twice (no plane; remotion rejects `.mp4`). `validate_output_name` /
dispatch stay frozen.
