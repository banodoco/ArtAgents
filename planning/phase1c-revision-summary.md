# Phase 1c — Codex (gpt-5.6-sol) plan revision from DeepSeek findings

Revised tasklist R1–R25 (M1: R1–R18, M2: R19–R25), 15 plan corrections, elegant approaches, potential issues, and one new exploration area A11 (pinned compositor parity).

Full text captured from codex phase-1c run; canonical copy of the revision lives in this directory as `phase1c-revision.md` (written next). Key deltas vs T1–T36:

- T1→R1 (freeze truth: 13.8667s visual / 98.0s all-track, unhashed MP3, dirty fence)
- T2→R2/R7 (compositor-parity timing + model)
- T3/T10→R3/R8/R9 (snapshot preimage, semantic vs display IDs, artifacts)
- T4→R4 (pure snapshot authority; bans show_timeline/repair loaders/head sidecar)
- T5→R4/R5 (one normalization boundary for assets; sources/-relative, no URL fallback)
- T6→R6 (managed-only selection; defer arbitrary standalone input)
- T8/T9→R7 (single normalized model + scopes)
- T12–T15→R10 (one layout model, both readings, 98s truth + visual-detail view)
- T16/T17→R12; T18/T19→R11 (two tiny render adapters, no SVG rasterizer)
- T21/T22/T7→R14 (packaging+SDK+retention together; requires_timeline:false, sorted timeline_ids)
- T23/T24→R15 (additive CLI after registry-sync; sessionless only for --from-view)
- T25–T27→R16–R18; T28→R19 (one durable transcript attachment); T29/T30→R20
- T31→R21 (ordered multi-image VLM transport), T32→R22 (scorer + existing agentic adapter)
- T33/T36→R23; T34/T35→R24; T36→R25

A11 (to explore now): `@banodoco/timeline-composition` v0.0.6 pinned by `remotion/package.json` — `lib/duration.ts` hold/speed + frame rounding, `TimelineComposition.tsx` reversed track painting; deliver small parity fixtures that become R2's contract.
