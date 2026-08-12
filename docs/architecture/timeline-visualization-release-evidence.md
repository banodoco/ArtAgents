# Timeline Visualization — Release Evidence

Epic: `timeline-visualization` (Aug 4; 2 milestones). Durable VLM-first
inspection surface: one stable command produces numbered PNG pages + versioned
JSON ground truth so an agent can understand a project's temporal structure
and text/speech evidence without ad-hoc commands.

## M1 — Navigation spine (PASS)

The complete visualization and snapshot-safe navigation spine through original
media.

- **Contracts**: compositor-parity duration helper (hold-overrides-trim, /speed,
  `Math.round` + 1-frame minimum, z-order reversal) + independent oracle,
  F1–F10 parity fixtures, SNS digest (canonical JSON, wall-time excluded),
  qualified-ref grammar (TL/SH/RG/CL/AS/TS/SP + `TL@time`), 7 artifact schemas,
  production structural validator.
- **Snapshot authority**: pure event-replay acquisition (head from event tail,
  registry from last replacement event, no repair/sidecar trust, concurrent-append
  retry, byte-immutable).
- **Model**: normalized inspection model (authored / frame / mounted / effective
  intervals, extents, paint order) + 7 cold scopes.
- **Layout + renderers**: one layout model (time-scaled + linear, 1920×1080,
  truthful 98s axis, 1-frame gap/overlap preserved), deterministic SVG + PNG
  with bundled font, pinned goldens + cross-runtime decoded-pixel proof.
- **Evidence pack**: self-contained (manifest, ground-truth, view-map,
  action-index, asset-index, transcript-index, diagnostics, reading-guide,
  metric-definitions, numbered PG##.png), hash-ledgered, pack-relative refs.
- **Executor + CLI**: `rendering.timeline_visualize` (requires_timeline:false,
  non-exempt), one-JSON stdout, narrow sessionless `--from-view` exception,
  run-owned evidence GC.
- **Frozen drill-down**: `--from-view --focus` resolves through the frozen ID
  map only, verifies every core hash + structural ref, never reads live state;
  `refresh_root` is the sole current-state transition.
- **Proof**: 43-test M1 matrix (compositor facts, stale sidecar, concurrent
  append, TOCTOU, invalid speed, registry drift, transition retiming, malformed
  IDs, tombstones, 500 clips, source-byte equality, renderer parity, --all,
  stdout purity, frozen lineage, immutability fence) + sequential fresh-agent
  journey + `docs/architecture/timeline-visualization-agent-navigation.md`.

## M2 — Source text and VLM proof (gates below)

- **Transcript attachment**: one durable project-owned reference (metadata
  home, hash-verified, no filename guessing, integrity states incl.
  uncontained).
- **TS/SP mapping**: `timeline = at + (source − from)/speed`, distinct SP per
  reuse, speaker/word-timing null states explicit, speech/caption/pixel-text
  lanes distinct, reciprocal TS→SP/CL↔SP action hierarchy.
- **Ordered VLM transport**: exact ordered PNG blocks (no contact sheet),
  pinned model, cost ceiling, full provenance (prompt/image hashes, response
  id, returned model, usage).
- **Scorer + harness**: frames exact, seconds tolerance explicit-only,
  parse/schema failures zero, identity-bearing 3-session aggregation (a failed
  session is a failure, never averaged), contained symlink-safe size-capped
  recursive evidence capture.
- **Adversarial corpus**: changed media/transcript, image order, model,
  resegmentation, clip removal, tombstone, malformed answers, snapshot drift —
  each detected through the real pipeline.
- **CI boundary**: hermetic default (`not integration and not opt_in and not
  live`), zero credential envs, live lane opt-in.

## Live VLM gate (R24)

- Transport: Grok 4.6 via the grok CLI (vision-capable; the user-directed hard-
  batch model).
- Image-only gate: 3 critical fixtures (journey, transcript, derived media),
  3 fresh sessions each, exact critical answers, ≥95% threshold.
- Discovery gate: fresh agent from CLI stdout → root → clip → original via
  generated actions.

_Results recorded in run evidence under `tests/packs/rendering/.r24-evidence/`
(gitignored) at gate execution time._

## Hermetic suite (end-to-end)

`pytest tests/packs/rendering/test_timeline_visualize_*.py
tests/core/timeline/test_timeline_*.py tests/packs/understanding/
tests/core/cli/test_timeline_visualize_cli.py -m "not live and not grok_iter"`
→ **494+ passed** (grok-UX geometry + background-probe fix applied).

## Commit trail (worktree `timeline-vlm-plan`)

- `29b648e` B1–B4 contracts/snapshot/model/layout/renderers
- `d30440a8` B5 evidence pack + executor + SDK + GC
- `9f44f6a8` B6 CLI + frozen drill-down
- `8dd4df32` B7 M1 matrix + journey + handoff doc
- `4717f7f5` B8 transcripts + VLM transport + TS/SP
- `b1c00505` B9 scorer + adversarial + CI boundary
- `6046c4e0` grok UX iteration + VLM gate transport
- `a1c74c4d` grok-driven zoom UX (real frames, tall lanes)
- `a9e9fbfa` background-probe fix
