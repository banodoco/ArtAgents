## Final tasklist

### M1 — Navigation spine

1. **R1 — Freeze truth and integration fences** — Files: `tests/fixtures/timeline_visualize/`, desert fixture, dirty-surface ownership map; deps: none; **M**. Acceptance: portable fixture freezes head v159, UUID/ULID/hashes, 24fps clip windows, authored visual-only end `13.8667s`, frame-quantized visual extent `332fr/13.8333s`, all-track composition `2352fr/98.0s`, unhashed MP3 state, and execution-time dirty ownership; storyboard behavior is characterized first.

2. **R2 — Freeze the compositor-parity contract** — Files: `astrid/core/timeline/duration.py`, render/validator/storyboard duration call sites, `docs/reference/timeline-composition-v0.0.6/`, `tests/fixtures/timeline_visualize/compositor_parity/`; deps: R1; **L**. Acceptance: one canonical helper plus an independent ~20-line Python oracle passes schema-valid F1–F8—hold-only, trim+speed, hold+speed, audio extension, muted extension, JS half-round/minimum-one-frame, transition bounds/default precedence, and z-order reversal—matching v0.0.6 without Remotion renders.

3. **R3 — Lock snapshot, schema, hash, and ID contracts** — Files: visualization schemas/contracts and timeline validation; deps: R1; **L**. Acceptance: versioned canonical-JSON `SNS` excludes wall time, stores timeline UUID+ULID and raw-hex hashes, separates semantic from lineage-local display IDs, and rejects duplicate track/clip IDs, dangling track references, and invalid timing domains including non-positive/non-finite speed.

4. **R4 — Build the pure snapshot authority** — Files: new `astrid/core/timeline/snapshot.py`, event/projection/display helpers; deps: R3; **XL**. Acceptance: one verified event read derives assembly, display, head, and latest registry, fully validates, retries concurrent changes, and leaves source bytes untouched; repairing loaders, sidecar head authority, and bridge repair are forbidden.

5. **R5 — Normalize and verify assets once** — Files: new `astrid/core/timeline/resolution.py`, integrity helpers; deps: R3, R4; **L**. Acceptance: contained `sources/` paths, source IDs/versions, roles, expected/observed hashes, and missing/mismatch/hash-unrecorded/remote/thumbnail states are explicit, with no URL, fetch, or thumbnail fallback.

6. **R6 — Pure managed timeline selection** — Files: snapshot selector, executor input adapter; deps: R4; **M**. Acceptance: named/default/all selection is ULID-backed, tombstone-aware, repair-free, and deterministic; managed directories and frozen manifests are supported while arbitrary standalone files remain deferred.

7. **R7 — Normalized inspection model and cold scopes** — Files: `timeline_visualize/src/model.py`, `scope.py`; deps: R2, R4–R6; **XL**. Acceptance: one model carries authored seconds, compositor frame intervals, transition-effective/clipped intervals, composition/visual/audio extents, FPS and compositor provenance, plus config and bottom-to-top paint indices—first visual config track is explicitly topmost—across every cold scope.

8. **R8 — Freeze semantic and display identities** — Files: `navigation.py`, ID-map tests; deps: R3, R7; **M**. Acceptance: canonical IDs are unique, display ordinals remain stable within a lineage, children copy the root map byte-for-byte, and refresh may create a new map without a tombstone ledger.

9. **R9 — Emit the semantic core and action graph** — Files: schemas, `ground-truth.json`, `action-index.json`, `asset-index.json`, empty-valid `transcript-index.json`, diagnostics, reading guide; deps: R8; **L**. Acceptance: artifacts validate independently and agree on IDs, FPS, authored/frame/effective metrics, paint indices, compositor version, transition-default fingerprint, root digest, and one recovery action per unavailable state.

10. **R10 — One layout model for both readings** — Files: `layout.py`, pagination, `view-map.json`; deps: R7–R9; **XL**. Acceptance: 1920×1080 time-scaled and linear pages preserve the truthful `2352fr/98s` axis, show frame-332 visual-detail geometry with `13.8667s` labeled only as authored time, retain the desert’s one-frame gap/overlap, display lanes topmost-first, and paint overlaps bottom-to-top in reversed visual config order.

11. **R11 — Deterministic SVG and PNG renderers** — Files: `render_svg.py`, `render_png.py`, bundled fonts, runtime contract; deps: R10; **L**. Acceptance: independent raw-SVG and Pillow adapters consume `LayoutPage`, agree with `view-map.json`, require no SVG rasterizer/system font, and pass pinned-runtime byte plus cross-runtime decoded-pixel tests.

12. **R12 — Verified source inspection and filmstrips** — Files: `assets.py`, `thumbnails.py`, source cards, ffmpeg sampling; deps: R5, R10, R11; **L**. Acceptance: originals and rendered sampling appear only after expected-hash verification, while approximation/missing/remote/unsupported states and sampling limits remain explicit and deterministic.

13. **R13 — Assemble and hash the evidence pack** — Files: `evidence_pack.py`, result manifest; deps: R9–R12; **L**. Acceptance: each self-contained pack records mandatory core artifacts, exact reading order, source hashes, metric definitions, FPS/compositor/registry provenance, and enough frozen truth for children to operate without parent or live project state.

14. **R14 — Package executor, finish SDK plumbing, own retention** — Files: executor metadata, `pack.yaml`, skill/capability index, SDK results, run ledger/GC; deps: R13; **XL**. Acceptance: `rendering.timeline_visualize` conforms without exemption, SDK returns full run/output identity, `requires_timeline:false` prevents timeline-manifest mutation, sorted `metadata.timeline_ids` supports `--all`, and explicit GC honors run-owned retention.

15. **R15 — Add the CLI/gateway façade additively** — Files: focused handler, `timeline_parser.py`, `timeline.py`, gateway gate; deps: R6, R9, R14; **L**. Acceptance: registry-sync work survives, `_resolve_edit_context()` handles project cold starts, only valid contained `--from-view` calls are sessionless, SDK invocation is mandatory, and stdout is one pointer-bearing JSON object.

16. **R16 — Snapshot-safe drill-down and refresh** — Files: frozen-manifest adapter, containment/hash preflight; deps: R4, R8, R13, R15; **L**. Acceptance: focus resolves only through the contained frozen ID map, verifies every core hash, never reads current timeline state, and exposes `refresh_root` as the sole current-state transition.

17. **R17 — M1 parity, determinism, and immutability matrix** — Files: model/layout/output/CLI fixtures; deps: R2–R16; **XL**. Acceptance: corrected F1–F8 and desert frame facts join stale-sidecar, concurrent append, media TOCTOU, invalid speed, registry drift, transition retiming/clipping, malformed IDs, tombstones, 500 clips, source-byte equality, renderer parity, `--all`, stdout purity, and frozen-lineage tests.

18. **R18 — Prove and document the M1 journey** — Files: dogfood run, `docs/architecture/timeline-visualization-agent-navigation.md`; deps: R17; **M**. Acceptance: a fresh agent navigates stdout → root → shot/range → clip → verified original → exact parent using generated actions, while documentation defines authored, frame-quantized, effective-rendered, visual-only, audible, and composition time unambiguously.

### M2 — Source text and VLM proof

19. **R19 — Establish one durable transcript attachment** — Files: transcribe/cut metadata, transcript schema, legacy diagnostics; deps: R18; **XL**. Acceptance: one versioned project-owned reference carries transcript hash, source-media identity/hash, producer/model provenance, and integrity without competing authority or filename guessing.

20. **R20 — Map TS/SP occurrences and render text evidence** — Files: `transcripts.py`, text lanes/pages/actions; deps: R7–R11, R19; **L**. Acceptance: transcript-hash-scoped TS IDs and distinct SP occurrences retain authored mapping and compositor-effective mapping—including transition-retimed visual media—while speaker/null/legacy, unavailable word timing, captions, speech, and uninspected pixel text remain distinct.

21. **R21 — Add ordered multi-image VLM transport** — Files: `understanding.visual_understand`; deps: R18; **L**. Acceptance: one request sends exact ordered PNG blocks without contact-sheet loss, preserves legacy behavior, pins model/settings/cost limits, and records prompt/image hashes, response ID, usage, and returned revision.

22. **R22 — Build the exact scorer and evidence harness** — Files: evaluator/scorer fixtures, existing `tests/agentic/adapter.py`; deps: R20, R21; **L**. Acceptance: schema validation precedes scoring, integer-frame facts score exactly, second-based tolerances apply only to explicitly named metrics, parse failures score zero, and recursive evidence capture remains contained, symlink-safe, and size-capped.

23. **R23 — Add adversarial fixtures and CI security boundary** — Files: fixtures, pytest markers, credential-free CI; deps: R22; **L**. Acceptance: changed media/transcripts/image order/model, resegmentation, removal, tombstone, malformed answers, and snapshot drift are covered while default CI strips credentials and excludes live/VLM work.

24. **R24 — Run separate image-only and discovery gates** — Files: live evaluation, Sisypy scenarios; deps: R23; **L**. Acceptance: both gates independently pass three fresh sessions per critical fixture, exact critical answers, and ≥95% overall; every failure becomes a fixture, invariant, or diagnostic.

25. **R25 — Live workflow, release evidence, and final docs** — Files: secret-scoped manual/nightly workflow, evidence retention/upload, command/skill docs; deps: R24; **M**. Acceptance: the epic runs through clean CI plus an authorized live lane, records reproducible evidence, and every documented command and invariant matches implementation.

## Changes this round

- **R1 now freezes three distinct desert facts:** authored visual-only `13.8667s`, frame-quantized visual `332/24=13.8333s`, and all-track composition `2352/24=98s`; the audio `[12,2352)` always determines total duration. (A11 §§1–2, §6)

- **R2 is now the closed compositor-parity contract**, depends only on R1, uses `duration.py`, snapshots the pinned source read-only, and replaces render tests with the independent Python oracle plus corrected F1–F8. F6 must catch JS half-frame rounding; F7 must use registered `cross-fade`, preserve explicit/registered/12-frame-fallback precedence, and test effective transition scheduling. (A11 §§1–4, §7, “Elegant simplifications”)

- **R3 now rejects invalid speed and structural references before duration calculation**, because `duration.ts` divides by raw `speed ?? 1`; its playback sanitizer is not the duration function. (A11 §1)

- **R7 now models authored, frame-quantized, and transition-effective intervals separately**, and carries both config order and bottom-to-top paint order; visual config track one is topmost. (A11 §§2–4, F7–F8)

- **R9/R13 now persist compositor version, FPS, registry/default fingerprint, metric definitions, extents, and paint indices**, preventing later evidence from silently changing meaning. (A11 §§0, 2–4)

- **R10 uses compositor frames for geometry** and explicitly separates topmost-first lane presentation from reversed bottom-to-top visual painting. (A11 §3, F8)

- **R17 absorbs F1–F8 and parity drift cases; R18/R20/R22 distinguish authored from rendered time**, so `13.8667s` and `13.8333s` cannot both satisfy an ambiguous “visual duration” answer. (A11 §§2, 4, 6–7)

No task, milestone boundary, dependency chain beyond R2’s completed-A11 cleanup, or size tag changes.

## Stability verdict

**STABLE — ready for conversion to batched execution plan**

No A12+ is warranted. The additional findings are bounded corrections inside the completed compositor-parity area.

## Plan corrections (updated)

- Replace normal CRUD repair with one pure event-replay/verification path; projection, display, head, and registry sidecars are caches or diagnostics, never authority. (A1)

- Define `SNS` as SHA-256 over a versioned canonical-JSON envelope; keep wall-clock creation only in operational run metadata. (A1, A10)

- Replace “16 seconds” with explicitly named metrics: authored visual-only `13.8667s`, compositor visual extent `332fr/13.8333s`, and all-track composition `2352fr/98s`; eliminate the Python planner’s erroneous `11.4333s` path. (A2, A11)

- Treat pinned compositor v0.0.6 as rendered truth and retain a read-only, provenance-bearing source snapshot; also fingerprint generated transition defaults because package version alone does not identify effective registry behavior. (A11)

- Use one core duration helper: numeric `hold` unconditionally overrides `from/to`, then duration divides by speed; validate positive finite speed before composition. (A11 §1)

- Convert starts and durations with JavaScript `Math.round`, enforce a one-frame minimum on duration, and never use Python’s banker-rounding `round()` as the oracle. (A11 §2)

- Compute composition duration from every clip with no track-kind, audio, muted, or metadata-duration exclusion; visual-only and audible spans are derived inspection metrics. (A11 §§1, 6)

- Resolve transitions as explicit frames → rounded explicit seconds → registered default → 12-frame fallback; transitions are same-track, overlap-bound, exclude `effect-layer` on both sides, and can retime or clip presentation relative to authored `at`. (A11 §4, F7)

- Encode z-order explicitly: visual tracks paint in reverse config order, making the first visual config track topmost; audio tracks are not reversed. (A11 §3, F8)

- Replace “extract helpers from storyboard” with clean `core/timeline` helpers; characterize the dirty storyboard first and limit its eventual change to importing the canonical duration function. (A2, A10, A11)

- Extend asset contracts with `sourceId`, `sourceVersion`, expected/observed hashes, and `hash_unrecorded`; computing a current hash does not retroactively verify the MP3. (A3)

- Require contained project-`sources/`-relative paths; never inherit timeline-relative, URL, remote-fetch, or thumbnail fallback. (A3, A10)

- Declare visualization runs `requires_timeline:false`, record sorted timeline IDs in run metadata, and use run-owned retention rather than mutating `manifest.json.contributing_runs`. (A3, A5)

- Permit a narrow sessionless gateway path only for validated, contained `visualize --from-view`. (A5)

- Capture both timeline UUID and ULID; display IDs are lineage-local, immutable in children, and may be reassigned only by a refreshed root. (A6)

- Fully validate after replay; reject duplicate authored identities, dangling track references, and invalid timing domains rather than inventing disambiguation or a tombstone-ID ledger. (A6, A11)

- Remove rasterized-SVG acceptance; verify raw SVG and PNG separately against `view-map.json`, bundle fonts, and pin the supported Pillow/runtime boundary. (A8)

- Extend the existing Astrid Sisypy adapter instead of creating another one. (A9)

- Replace contact-sheet VLM evaluation with ordered image blocks on the canonical understanding surface and pin an explicit model instead of `best`. (A7)

- Defer arbitrary `timeline + assets_registry` executor input until a real owned caller exists. (A5)

- Treat `timeline_storyboard`, dirty `ClipAddedPayload.start/duration`, projection, `_resolve_edit_context`, and registry-sync work as upstream baseline; shared parser/pack edits land additively after those changes. (A10)
