### B1 — Frozen truth and contracts

- Tasks:
  - R1 [FLASH] — Freeze truth and integration fences. Deps: none.
  - R2 [HARD] — Freeze compositor parity. Deps: R1.
  - R3 [HARD] — Lock snapshot, schema, hash, and ID contracts. Deps: R1.
- Parallel/sequence: R1 runs first and alone. R2 and R3 are DAG-independent, but serialize `R1 → R2 → R3` in the shared worktree because their validation/call-site surfaces overlap. This scheduling lock is not a new dependency.
- Handoff artifact: portable desert and F1–F8 fixtures under `tests/fixtures/timeline_visualize/`; dirty-surface ownership map; `duration.py`; provenance-bearing v0.0.6 source snapshot; schemas and negative fixtures. Minimum test log: contract, parity, canonical-hash, identity, and invalid-timing tests.
- Surveyor check: independently recompute the three desert facts; compare production duration results against an oracle that imports no production code; prove JS half-rounding without Python `round()`; validate registered `cross-fade`, all transition-default precedence paths, z-order reversal, duplicate/dangling IDs, and zero/negative/NaN/infinite speed.
- Oracle check-in questions:
  1. Are authored visual-only `13.8667s`, compositor visual `332fr/13.8333s`, and all-track composition `2352fr/98s` distinct and correctly named?
  2. Do schema-valid F1–F8 match compositor v0.0.6 for hold-before-speed, all clips including muted/audio, one-frame minimum, JS rounding, transition scheduling/clipping/defaults, and reversed paint order?
  3. Is SNS a versioned canonical-JSON envelope excluding wall time, with UUID, ULID, raw-hex hashes, and separate semantic/display identities?
  4. Are structural and timing errors rejected before duration arithmetic?
  5. Did work respect the R1 dirty-surface fence and characterize storyboard before its sole permitted duration-import change?

### B2 — Pure snapshot acquisition

- Tasks:
  - R4 [HARD] — Pure snapshot authority. Deps: R3.
  - R5 [FLASH] — Normalize and verify assets. Deps: R3, R4.
  - R6 [FLASH] — Managed timeline selection. Deps: R4.
- Parallel/sequence: R4 first; then R5 and R6 in parallel with asset-resolution and selection file ownership separated.
- Handoff artifact: `snapshot.py`, `resolution.py`, selector/adapter changes; stale-sidecar, concurrent-append, containment, asset-state, tombstone, and selection fixtures. Include recursive source-byte SHA-256 manifests from before and after all read operations.
- Surveyor check: monkeypatch every mutating API to fail; inject an append between reads; randomize directory enumeration; test named/default/all selection, traversal, symlinks, URL paths, missing/mismatch/hash-unrecorded/remote/thumbnail states, and source-byte equality.
- Oracle check-in questions:
  1. Does one verified event read derive assembly, display, head, and latest registry, then fully validate the result?
  2. Are repairing loaders, bridge repair, sidecar head authority, and all write-on-read paths absent?
  3. Does a concurrent change cause a complete retry rather than a mixed-generation snapshot?
  4. Is a current hash without a recorded expected hash still `hash_unrecorded`?
  5. Are selections deterministic, ULID-backed, tombstone-aware, repair-free, and limited to managed directories/frozen manifests?

### B3 — Normalized semantics and navigation core

- Tasks:
  - R7 [HARD] — Normalized inspection model and cold scopes. Deps: R2, R4, R5, R6.
  - R8 [FLASH] — Semantic and display identities. Deps: R3, R7.
  - R9 [FLASH] — Semantic core and action graph. Deps: R8.
- Parallel/sequence: strict `R7 → R8 → R9`.
- Handoff artifact: `model.py`, `scope.py`, `navigation.py`; ID-map fixtures; validating `ground-truth.json`, `action-index.json`, `asset-index.json`, empty-valid `transcript-index.json`, diagnostics, and reading guide.
- Surveyor check: validate every JSON artifact independently, then perform a cross-artifact join over IDs, metrics, extents, paint indices, compositor/default fingerprints, and root digest. Byte-compare root/child ID maps and count exactly one recovery action per unavailable state.
- Oracle check-in questions:
  1. Are authored, frame-quantized, and transition-effective/clipped intervals separate?
  2. Are composition, visual-only, and audio/audible extents separately named across every cold scope?
  3. Are config order, first-track-topmost semantics, and bottom-to-top paint indices explicit?
  4. Are canonical IDs unique and lineage-local display ordinals immutable in children?
  5. Can every semantic artifact be interpreted without parent or live-project state?

### B4 — Truthful geometry and deterministic rendering

- Tasks:
  - R10 [HARD] — Shared layout model. Deps: R7, R8, R9.
  - R11 [FLASH] — Deterministic SVG and PNG renderers. Deps: R10.
- Parallel/sequence: strict `R10 → R11`.
- Handoff artifact: `layout.py`, pagination, `view-map.json`, raw-SVG and Pillow adapters, bundled fonts, runtime contract, and golden layout/render fixtures.
- Surveyor check: recompute every view-map box from `LayoutPage`; verify the `2352fr/98s` axis, frame-332 detail boundary, authored-only `13.8667s` label, and one-frame desert gap/overlap. Render twice under the pinned runtime for byte equality, compare decoded pixels under the supported alternate runtime, and run without system fonts or an SVG rasterizer.
- Oracle check-in questions:
  1. Is all geometry based on compositor frames rather than ambiguous seconds?
  2. Are lanes topmost-first while overlaps paint bottom-to-top in reversed visual config order?
  3. Do both time-scaled and linear readings preserve the truthful 98-second axis?
  4. Are SVG and PNG genuinely independent `LayoutPage` consumers?
  5. Is rasterized-SVG acceptance impossible, with pinned runtime and bundled-font boundaries explicit?

### B5 — Verified evidence product

- Tasks:
  - R12 [FLASH] — Verified source inspection and filmstrips. Deps: R5, R10, R11.
  - R13 [FLASH] — Assemble and hash the evidence pack. Deps: R9, R10, R11, R12.
  - R14 [HARD] — Package executor, SDK plumbing, and retention. Deps: R13.
- Parallel/sequence: strict `R12 → R13 → R14`.
- Handoff artifact: `assets.py`, `thumbnails.py`, source cards, `evidence_pack.py`, result manifest, executor metadata, `pack.yaml`, regenerated capability/skill index, SDK result changes, run ledger, and GC tests. Include a copied pack proven functional outside its parent project.
- Surveyor check: mutate media between verification and sampling; cover missing, mismatch, unrecorded, remote, unsupported, and sampling-limit states. Validate every manifest hash and mandatory artifact. Assert executor conformance without exemption, full SDK identities, `requires_timeline:false`, sorted `metadata.timeline_ids`, byte-unchanged timeline manifests, and run-owned GC.
- Oracle check-in questions:
  1. Can originals or rendered samples appear only after expected-hash verification, including TOCTOU protection?
  2. Are remote and thumbnail fallbacks impossible?
  3. Is the pack self-contained with exact reading order, hashes, metric definitions, FPS/compositor/registry provenance, and sufficient frozen truth for children?
  4. Does the executor conform without an exemption and return complete run/output identity?
  5. Does retention avoid `manifest.json.contributing_runs` and every other timeline mutation?

### B6 — Secure CLI and frozen drill-down

- Tasks:
  - R15 [HARD] — Additive CLI/gateway façade. Deps: R6, R9, R14.
  - R16 [HARD] — Snapshot-safe drill-down and refresh. Deps: R4, R8, R13, R15.
- Parallel/sequence: strict `R15 → R16`.
- Handoff artifact: additive `timeline_parser.py`/`timeline.py` changes, focused handler, gateway gate, frozen-manifest adapter, containment/hash preflight, and CLI/SDK integration fixtures.
- Surveyor check: parse stdout as exactly one JSON value with no trailing content; exercise project cold starts and SDK invocation; fuzz traversal, nested symlinks, outside paths, and hash-mismatched `--from-view`; prove invalid calls remain session-gated. Mutate live state after root creation while monkeypatching current-state readers to fail during drill-down.
- Oracle check-in questions:
  1. Did registry-sync, `_resolve_edit_context()`, clip start/duration, projection, storyboard, and pack changes integrate additively?
  2. Is only a valid, contained `visualize --from-view` call sessionless?
  3. Is SDK invocation mandatory and stdout a single pointer-bearing JSON object?
  4. Does drill-down use only the frozen ID map and verify every core hash?
  5. Is `refresh_root` the sole transition back to current state?

### B7 — M1 closure and milestone gate

- Tasks:
  - R17 [FLASH] — M1 parity, determinism, and immutability matrix. Deps: R2–R16.
  - R18 [FLASH] — Prove and document the M1 journey. Deps: R17.
- Parallel/sequence: strict `R17 → R18`. No M2 task may start before this oracle PASS.
- Handoff artifact: complete matrix fixtures/results, two-run output hashes, before/after source-byte manifests, dogfood pack and journey transcript, and `docs/architecture/timeline-visualization-agent-navigation.md`.
- Surveyor check: none separately—R17 is deliberately the Flash-owned independent survey of the implementation. Its full command log and evidence replace a redundant surveyor pass.
- Oracle check-in questions:
  1. Does R17 cover corrected F1–F8 and every named stale-sidecar, append-race, TOCTOU, invalid-speed, registry-drift, transition, malformed-ID, tombstone, 500-clip, renderer-parity, `--all`, stdout, immutability, and frozen-lineage case?
  2. Are repeated outputs deterministic and all source bytes unchanged?
  3. Can a fresh agent navigate stdout → root → shot/range → clip → verified original → exact parent using generated actions only?
  4. Do the docs distinguish authored, frame-quantized, effective-rendered, visual-only, audible, and composition time unambiguously?

### B8 — Transcript semantics and ordered VLM transport

- Tasks:
  - R19 [HARD] — Durable transcript attachment. Deps: R18.
  - R20 [HARD] — TS/SP occurrences and text evidence. Deps: R7–R11, R19.
  - R21 [HARD] — Ordered multi-image VLM transport. Deps: R18.
- Parallel/sequence: start R19 and R21 in parallel after the M1 PASS. Begin R20 after R19 while R21 may continue; join all three before review.
- Handoff artifact: transcript reference/schema/legacy diagnostics; `transcripts.py`, text lanes/pages/actions; `visual_understand` changes; captured request and provenance fixtures.
- Surveyor check: rename/delete guessed transcript filenames, tamper transcript/source hashes, resegment occurrences, exercise unavailable word timing and transition-retimed media. Capture the outbound VLM request and byte-compare ordered PNG blocks; verify legacy behavior and every provenance field.
- Oracle check-in questions:
  1. Is there exactly one project-owned, versioned transcript authority containing transcript/source hashes, source identity, producer/model provenance, and integrity?
  2. Are legacy cases diagnostics rather than alternate authority?
  3. Are TS IDs transcript-hash-scoped and SP IDs occurrence-specific?
  4. Are authored and compositor-effective mappings both retained without conflating captions, speech, speaker/null/legacy, and uninspected pixel text?
  5. Does one request preserve the exact PNG order without contact-sheet loss while pinning model/settings/cost and recording prompt/image hashes, response ID, usage, and returned revision?

### B9 — Exact scoring and hermetic adversaries

- Tasks:
  - R22 [HARD] — Exact scorer and evidence harness. Deps: R20, R21.
  - R23 [FLASH] — Adversarial fixtures and CI security boundary. Deps: R22.
- Parallel/sequence: strict `R22 → R23`.
- Handoff artifact: evaluator/scorer corpus, extended `tests/agentic/adapter.py`, recursive evidence fixtures, adversarial cases, pytest markers, and credential-free CI logs.
- Surveyor check: test exact frames, explicitly tolerated seconds, boundary values, malformed/partial/schema-invalid answers, traversal, nested symlinks, oversized trees/files, and recursive capture caps. Run `ASTRID_CI_SKIP_COVERAGE=1 bash scripts/reshape/run_ci_checks.sh` with sentinel credentials and prove secrets are stripped and no live/VLM test is selected.
- Oracle check-in questions:
  1. Does schema validation precede scoring, with every parse/schema failure scoring zero?
  2. Are integer frames exact and second tolerances restricted to explicitly named metrics?
  3. Is recursive evidence capture contained, symlink-safe, size-capped, and implemented by extending the existing adapter?
  4. Are changed media/transcript/image order/model, resegmentation, removal, tombstone, malformed answers, and snapshot drift covered?
  5. Is default CI genuinely credential-free and structurally unable to enter the live lane?

### B10 — Independent gates and release

- Tasks:
  - R24 [FLASH] — Separate image-only and discovery gates. Deps: R23.
  - R25 [FLASH] — Live workflow, release evidence, and final docs. Deps: R24.
- Parallel/sequence: strict `R24 → R25`; R25 is the final epic task.
- Handoff artifact: per-fixture/per-session evidence for both gates, score aggregation, promoted regression cases, clean-CI proof, authorized live workflow run, retained release evidence, and command/skill documentation.
- Surveyor check: mechanically prove each gate used three fresh sessions per critical fixture, independently achieved exact critical answers and ≥95% overall, and retained complete evidence. Smoke-run every documented command and scan retained artifacts/logs for secrets.
- Oracle check-in questions:
  1. Did image-only and stdout-discovery gates pass independently without shared context?
  2. Did every critical fixture pass all three fresh sessions with exact critical answers and ≥95% overall?
  3. Did every failure become a fixture, invariant, or actionable diagnostic before rerunning?
  4. Does R25 prove clean credential-free CI plus a separately authorized, secret-scoped manual/nightly lane?
  5. Is evidence reproducible and retained, and do all documented commands/invariants match implementation?

## EXTREMELY HARD task roster

| Task | Why it needs gpt-5.6-sol | Risk if Flash attempts it |
|---|---|---|
| R2 | Reconstructs exact JS compositor behavior across timing, transitions, rounding, and paint order. | A plausible but incompatible Python model becomes the foundation. |
| R3 | Designs SNS, identity layers, canonical hashing, and the pre-arithmetic validation boundary. | Unstable hashes, ambiguous IDs, or unsafe timing values leak downstream. |
| R4 | Combines replay authority, concurrency, validation, cache distrust, and zero write-on-read behavior. | Stale/mixed snapshots or silent repairs become authoritative. |
| R7 | Unifies several non-equivalent time domains, extents, scopes, and orderings. | Individually valid artifacts disagree semantically. |
| R10 | Converts compositor truth into two novel geometries without losing frame artifacts or z-order. | Attractive but factually false visualizations. |
| R14 | Crosses executor contracts, SDK identity, metadata, capability registration, and retention. | Exemptions, incomplete results, or timeline-manifest mutation. |
| R15 | Changes a dirty CLI/gateway boundary while introducing a narrowly scoped sessionless exception. | Baseline work is clobbered or arbitrary paths bypass session gating. |
| R16 | Enforces the frozen-lineage/current-state security boundary and hash/containment preflight. | Drill-down quietly reads live state or accepts tampered packs. |
| R19 | Establishes the single durable transcript authority across producer and source-media provenance. | Filename guessing or competing authorities produce stale associations. |
| R20 | Designs occurrence identity and authored/effective mapping through transition-retimed media. | Resegmentation breaks IDs or rendered-time evidence becomes wrong. |
| R21 | Alters canonical VLM transport while preserving order, legacy behavior, cost limits, and provenance. | Contact-sheet loss, reordered images, compatibility regressions, or unauditable calls. |
| R22 | Couples exact epistemic scoring with a hostile filesystem evidence boundary. | Inflated scores, tolerance leakage, or symlink/size containment escapes. |

## Oracle protocol

At every checkpoint, use a fresh gpt-5.6-sol review context; a HARD-task implementation session cannot certify its own work.

1. Read the literal acceptance criteria and all consolidated corrections before the diff.
2. Review only the delta since the previous PASS, plus any reopened earlier contract.
3. Verify exact direct dependencies and the R1 dirty-surface ownership map.
4. Map every acceptance clause to implementation, positive test, negative test, and reproducible evidence.
5. Rerun the highest-risk focused tests and inspect generated artifacts directly; narrative claims are not evidence.
6. Check schemas, cross-artifact joins, hashes, determinism, immutability, containment, stdout purity, and provenance.
7. Search specifically for forbidden shortcuts: repair loaders, sidecar authority, URL/thumbnail fallback, Python banker-rounding, SVG rasterization, system fonts, timeline-owned retention, blanket sessionless access, live-state child reads, contact sheets, unpinned `best`, or a second Sisypy adapter.
8. Emit only:
   - `PASS`, or
   - `FAIL` with task ID, owner model, violated acceptance clause, exact evidence, affected file/artifact, required behavior, fix instructions, and rerun command.
9. On FAIL, return each issue to its original owner class—Flash or SOL—then repeat the surveyor and oracle checks. Touching a previously passed contract reopens its relevant checks.

## Risks in the execution structure

- The dirty ground-truth checkout is moving integration state, not a safe implementation surface. R1 must regenerate its ownership map immediately before execution; later batches must use that frozen map and never mutate the ground-truth checkout.
- Logical independence does not imply safe shared-worktree concurrency. Only R5/R6 and R19/R21 are approved parallel fronts. Any additional parallelism requires isolated worktrees and explicit file ownership.
- R7 is a four-way join; R17 is the total M1 join over R2–R16; R22 joins R20 and R21. Starting at “mostly complete” would invalidate downstream evidence.
- The M1 boundary is absolute: code landing for R18 is insufficient; B7 requires oracle PASS before any M2 work.
- Production code and parity tests could share the same mistake. R2 therefore requires both a pinned source snapshot and a genuinely independent oracle that imports no production helper.
- B8 concentrates three HARD tasks. Preserve its parallel roots, but do not let R22 begin until the complete R19/R20/R21 checkpoint passes.
- Live VLM variance must never be averaged away. Each failed fresh session is a failure requiring a fixture, invariant, or diagnostic before rerun.
- Hermetic and live CI are separate security domains. Default CI must strip credentials and exclude live work; only the explicit manual/nightly lane may receive scoped secrets.
- Evidence growth could undermine containment and retention. Keep evidence hash-addressed, size-capped, run-owned, and governed by R14’s GC contract.
