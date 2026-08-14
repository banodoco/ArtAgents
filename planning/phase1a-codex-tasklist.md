# Phase 1a — Codex (gpt-5.6-sol, max) tasklist + exploration areas

Generated 2026-08-11 by `codex exec --sandbox read-only` from
`/tmp/codex_phase1a.md`. Source of truth for the exploration phase.

## Key planning discoveries (from Codex's repo pass)

- The brief's "16-second" desert fixture actually spans ~98 seconds once its audio hold is included → duration semantics task required (T2).
- The normal timeline read path (`show_timeline()`) can repair/write projections — visualization must use a read-only event-sourced snapshot path (T4).
- The dirty/untracked baseline has ~137 paths including `timeline_storyboard`; integration collision is a first-class concern (A10).

## 1. Tasklist (T1–T36)

1. **T1** Freeze the acceptance baseline [M] — fixture matrix records exact event heads, registry/media hashes, expected scopes; resolves the 16s-vs-98s duration claim.
2. **T2** Unify temporal and layering semantics [L, after T1] — one tested helper defines hold/trim/speed/boundaries/transitions/track order/active stack across validation, rendering, visualization.
3. **T3** Lock artifact schemas, versions, ID grammar [L, after T1] — Draft-07 schemas per artifact; reject invalid versions/IDs/reading order/dangling refs.
4. **T4** Read-only event-sourced snapshot API [XL, after T1] — replay+verify identity, checkpoints, head/version/hash; retry concurrent changes; diagnose stale sidecars; no project byte changes.
5. **T5** Authoritative asset-registry snapshot + resolver [XL, after T3+T4] — classify verified original / missing / hash-mismatch / remote / thumbnail-only; no fetch, substitution, URL leakage, implicit pruning.
6. **T6** Supported timeline input adapters [L, after T4+T5] — managed + interchange forms normalize identically; tombstones/ambiguous slugs/malformed dirs fail with one recovery command.
7. **T7** Repair SDK and managed-run result plumbing [L, after T3] — explicit/attached invocations expose run_id, run_root, outputs, executor version, manifest_path without polluting stdout.
8. **T8** Normalized inspection model [XL, after T2+T4–T6] — renderer-independent model of tracks/clips/gaps/transitions/effects/assets/layers/durations/provenance/hashes.
9. **T9** Cold scope selection [L, after T8] — project/all/timeline/shot/range/clip/asset/timestamp selectors, deterministic subsets, context/neighbor behavior.
10. **T10** Frozen identities + navigation graph [L, after T3+T4+T9] — stable-ID map, action index, snapshot lineage, qualified-reference parser.
11. **T11** Semantic inspection bundle first [L, after T8+T10] — ground-truth, asset index, action index, transcript placeholder, diagnostics, reading guide; schema-valid byte-stable.
12. **T12** Shared page/layout primitives [L, after T8+T9] — one coordinate model; 1920×1080 pages; typography/lane minimums; clipping; deterministic reading order.
13. **T13** Time-scaled layout [L, after T12].
14. **T14** Linear layout [M, after T12].
15. **T15** Pagination, continuation, view mapping [L, after T13+T14] — view-map.json; deterministic numbered pages.
16. **T16** Verified media + source cards [L, after T5+T12].
17. **T17** Source and rendered filmstrips [L, after T5+T12+T16] — ≤36 candidates, ≤12 frames/page; rendered frames only when hash-verified.
18. **T18** Raw SVG output [M, after T15–T17] — byte-stable, parity with view-map.
19. **T19** Deterministic PNG output [L, after T15–T17] — byte-identical pinned runtime, pixel-equivalent cross-platform.
20. **T20** Assemble + hash complete evidence pack [L, after T11+T18+T19].
21. **T21** Evidence retention + GC [M, after T7+T20] — bundle survives documented GC; removed only via explicit lifecycle op.
22. **T22** Package + register `rendering.timeline_visualize` [M, after T20+T21].
23. **T23** `astrid timelines visualize` CLI [L, after T6+T7+T22].
24. **T24** Gateway, session, task-gate semantics [L, after T23].
25. **T25** Snapshot-safe drill-down [L, after T10+T20+T23+T24] — --from-view/--focus, hash verify, frozen lineage, refresh-root only.
26. **T26** M1 deterministic test matrix [XL, after T2–T25].
27. **T27** Prove + document M1 journey [L, after T26] — dogfood run + agent-navigation handoff doc.
28. **T28** Durable transcript attachment contract [XL, after T27] — versioned transcripts with source identity/hash + explicit provenance; no filename/CWD guessing.
29. **T29** Transcript occurrence mapping [L, after T28] — timeline_time = clip.at + (source_time - clip.from)/clip.speed; TS + SP occurrences.
30. **T30** Authored-text + speech inspection pages [L, after T19+T29].
31. **T31** VLM evaluation model contract [L, after T27] — separate ordered PNG inputs (not contact sheet); evidence records model revision, detail, limits, response ID, usage, page hashes.
32. **T32** Exact VLM scorer + evidence harness [L, after T30+T31] — exact critical answers, ±0.05 s timing, 95% aggregate, session identity, hashes.
33. **T33** Adversarial freshness + integrity fixtures [L, after T29–T32].
34. **T34** Image-only M2 gate [M, after T33] — 3 consecutive fresh sessions, ≥95%.
35. **T35** Fresh-agent stdout-discovery gate [L, after T25+T30+T32] — Sisypy scenario, recursive evidence capture.
36. **T36** CI, docs, release evidence [L, after T34+T35].

## 2. Exploration areas (A1–A10, ranked)

- **A1 — Atomic, read-only snapshot authority.** How assembly.jsonl + checkpoints + assembly.head.json + assembly.json + projected registry read as one coherent root; show_timeline() repair path; LocalFsBackend.head() stale-sidecar trust; pure replay + retry sufficiency; concurrent-append detection; exact frozen-root bytes/hashes.
- **A2 — Canonical duration + compositor truth.** Conflicting duration helpers (validators, rendering.render, timeline_storyboard, Remotion); desert timeline images end ~13.87s but audio extends to ~98s; how hold/trim/speed/transitions/muted tracks/audio/layer order affect duration, active stacks, range selection, pagination.
- **A3 — Registry, source, integrity, retention authority.** registry.json, registry-replaced events, resolved assets.json, project sources.json, final outputs, bridge recovery; sourceId/sourceVersion schema drift; unhashed MP3; original definition; authoritative hash; remote/derived roles; GC survival.
- **A4 — Durable transcript provenance.** editorial.transcribe → video_editing.cut → hype.metadata.json → project sources → managed timeline; transcript lacks version/source identity; reference may live in a run artifact resolved relative to CWD; durable attachment point; segment identity; post-replacement provenance; absent word timing/speaker/transcript/audio.
- **A5 — CLI, ownership, run-ledger semantics.** gateway parsing → session/task gates → handler façade → SDK invocation → executor re-entry → run finalization; --from-view sessionless safety; --all multi-timeline run records; interchange ownership; attached vs explicit observability without stdout pollution.
- **A6 — Stable IDs, snapshot lineage, artifact evolution.** TL/TR/SH/... grammar vs duplicate slugs, tombstones, reused segments, pagination, reordered tracks, refreshed roots; semantic vs occurrence IDs; post-refresh stability; child ancestry proof; independent artifact evolution.
- **A7 — VLM transport + model identity.** visual_understand extension vs narrow Responses-API evaluator; contact-sheet readability destruction; presets bypass generation-only catalog; ordered-image limits, detail, requested-vs-actual revision, structured-output validation, retry/session isolation, cost ceilings, evaluation-profile registry.
- **A8 — Rendering determinism + information density.** prototype sparse/dense/overlap/transcript-heavy/long-audio pages at 1920×1080; Pillow loose pinning; environment-selected fonts; SVG rasterizer absence; supported-platform guarantee; bundled font; SVG/PNG parity method; max readable density; pagination-vs-compression.
- **A9 — CI + evidence-capture boundaries.** credential-free CI vs opt-in live evaluation; ffmpeg present but no VLM credentials; Sisypy non-recursive evidence capture; artifact retention; secrets/cost controls; freshness proof; nightly/release triggers; 3-session demonstration; failure→fixture rule.
- **A10 — Integration collision with dirty initiatives.** unregistered timeline_storyboard, pluggable-renderer work, asset-library proposals, ~137 dirty/untracked paths; helpers to extract only after semantic correction; overlapping pack/schema files; merge order; ownership boundaries; storyboard's remote fallback/timestamps/positional-ID policies.
