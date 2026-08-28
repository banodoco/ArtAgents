# Completion matrix — megado run ffmpeg-text (base c6c505af → HEAD 88937480)

## Model declaration (user-pinned, honored throughout)
Grok 4.6 = planner/revision/tasklist/oracle/`[XHARD]` · GLM 5.3 Flash = explorers/critics/normal executors. Zero `[XHARD]` (oracle-finalized at freeze). No model switches occurred.

## Agent-goal done criteria → evidence

| # | Criterion | Evidence | Result | Reviewer disposition |
|---|---|---|---|---|
| 1 | Media+text timeline renders through `rendering.ffmpeg` (text visible, positioned, timed, faded; output plays) | `.oracle/evidence/batch-5-live-smoke.txt` — authoritative T7 host run: **1 passed in 11.12s**; re-verified post-R1 (1.92s). Real lavfi plate + sine audio + text window [1,2], fades 0.2/0.2; guards: finite ffprobe duration, mid-window ink, post-END luma ≈ pre-AT. | **PASS** | B5 check-in PASS; re-review pass 3 PASS (line-verified guards) |
| 2 | `support.py` accepts renderable media+text; fail-closed otherwise | 15 fail-closed reject cases + accept cases (B2 + R1: text-past-spine, fade-vs-window, text `from`, x/y, audio-track, text-card, missing font, extra visual media, non-fade effects…); B2 check-in PASS; R1 re-review PASS | **PASS** | Grok B2: PASS; Grok re-review: PASS |
| 3 | `renderer.yaml` matches implemented reality | yaml dict-equality test (B4); clip_types retarget in-commit; re-review pass 3: "yaml … matches the overlay path; media fades still fail-closed" | **PASS** | B4 check-in PASS (ACs 1-10 with line evidence) |
| 4 | `pytest tests/packs/rendering/` passes; no regressions in touched surfaces | New-file tests 11→(final) full file green; triple gate 91 passed post-R1; `test_cli.py` 16 passed; full-pack sweep classification: 52 pre-existing environmental failures at base (zero-tracked-diff argument; facade subset stash-verified identical at B2 HEAD); ffmpeg/text surface 0 failures throughout | **PASS** (with recorded pre-existing environmental failure set, unchanged from base) | B1/B3 check-ins PASS; executor stash-verification |
| 5 | Live render smoke (real ffmpeg) | T7 host run (above); hang regression guarded by `-t END` cap + finite-duration assertion (E1 defect class closed in R1: d=0 fades now omitted per side) | **PASS** | T7 + re-review |
| 6 | Docs match shipped behavior | B6 commit a5fc84f8; B6 check-in verified every claim against code (incl. `LegacyRenderRoutingWarning`, blur sigma, stream-copy gating); forbidden claims absent | **PASS** | B6 check-in PASS |

## North Star alignment disposition (final)
- Simplest sufficient toolchain: one ffmpeg binary + in-tree Pillow; no Chrome/webpack/CDN/drawtext/font subsystem. **Advanced.**
- Capability-driven routing: yaml, support, and filtergraph updated together; fail-closed everywhere (including R1's two new rejects); default `rendering.render` auto-route now truthfully picks ffmpeg for media+text (Remotion = fail-closed fallback, recorded in provenance). **Advanced.**
- Output parity: ThreeTimelineComposition bar (fixed stack, anchor/wrap/shadow, clip fades); R1 removed the last silent alpha divergence (d=0 ease). **Advanced.**
- Offline/fast by default: renders work without network; smoke renders in seconds. **Advanced.**
- Anti-patterns: none reproduced (no routing lies, no yaml/support lag, no speculative layers, no silent fallbacks, no scope creep). Residual cosmetic: doc schematic draws fade-present shape (explicitly not a criterion miss).

## Known limitations (documented, not defects)
- `text.fontFamily`/`italic` ignored (fixed Arial/DejaVu stack) — disclosed in doc; parity bar decision.
- Text always renders above media (slide-overlay semantics); track-order layering divergence vs Remotion noted in final review, disposed.
- Pre-existing environmental suite failures on this machine (missing `remotion/node_modules`; real-render timeouts >120s/>600s; timeline_visualize golden drift) — unchanged from base, zero-tracked-diff argument + stash verification.

## Stop condition
`complete` — all done criteria PASS under final independent review (pass 3 of 3). Sync authorized per agent_goal (branch push only).
