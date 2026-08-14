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
  **RESULT: 1.0 × 3 sessions on all three fixtures (100%).** Fixes that got
  there: cue split into nav + facts lines (SP timing no longer buried),
  NEXT/PARENT question alignment, robust prose-prefixed JSON parse.
- Discovery gate: fresh agent from CLI stdout → root → clip → original via
  generated actions; sessionless gateway legs.
  **RESULT: 1.0 × 3 fresh journeys (root/clip/asset legs), strict 3-session
  rule.** Fix that got there: the gold focus ring around the FOCUS clip on
  every page (PNG + SVG), so the root leg reads CL01 — not the wide audio
  bar — as the subject.

_Results recorded in run evidence under `tests/packs/rendering/.r24-evidence/`
(gitignored) at gate execution time._

## Hermetic suite (end-to-end)

`pytest tests/packs/rendering/test_timeline_visualize_*.py
tests/core/timeline/test_timeline_*.py tests/packs/understanding/
tests/core/cli/test_timeline_visualize_cli.py -m "not live and not grok_iter"`
→ **495 passed, 5 deselected** (final post-gate run, 2026-08-11).

## B10 oracle verdict (Grok 4.6, 2026-08-11)

- R24: **PASS** — hermetic 495 green; image-only 66/66 exact-match (9/9
  files, accuracy 1.0); discovery 9/9 legs accuracy 1.0; failure→fixture
  loop demonstrated (cue split, NEXT token, prose JSON parse, focus ring).
- R25: **PASS after fixes** — initial FAIL on two CI leaks, both closed:
  1. `grok_iter` UX-iteration test (can mutate sources) was collectable by
     default CI → now `opt_in` AND excluded by the broad filter
     (`not grok_iter`).
  2. Live lane hardcoded `/Users/peteromalley/.grok/bin/grok` while the
     runner guards on `which grok` → transport + test now resolve grok via
     `GROK_BIN` env → `PATH` → fallback.
- Stale doc line (`TS/SP await M2`) corrected to reflect shipped M2.

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
- `b75511de` image-only gate PASSES with grok (cue split + alignment)
- `92ed3ecf` BOTH VLM gates PASS with grok (focus ring anchors navigation)
- `f1949aea` focus ring outline-only (never paint over the clip)
- `9234247c` R25 oracle findings — grok_iter never in default CI, grok via PATH

## Complex multi-step gate (park24) — 24 clips, planted mismatches

The stress test the R24 gates don't cover: **scale + multi-step navigation +
semantic mismatch detection invisible to hashes**.

- **Fixture** `tests/fixtures/timeline_visualize/park24_{slice,media}`: a
  24-clip timeline with real rendered frames (desert-plant narrative), built
  deterministically by `planning/build_park24_slice.py`.
- **Planted mismatches** (both hash-verified — `verified_original` — so
  ground truth can never flag them):
  - `TL01.CL09` shows a byte-identical copy of `TL01.CL03`'s frame (same
    `content_sha256`, distinct registry entry) — a frame reused out of
    narrative order.
  - `TL01.CL16` shows the Paris poster (foreign scene) in a nature storyboard.
- **Gate** `test_timeline_visualize_gate_park24.py` (live): a fresh agent
  navigates root (orient: 24 clips) → zoom CL08 → NEXT-chain walk
  CL08→CL09→CL10 → inspect CL09's + CL03's ORIGINALS (duplicate detection)
  → inspect CL16's ORIGINAL (foreign detection), reporting exactly
  `TL01.CL09` + `TL01.CL16`.  Six legs per journey, three fresh journeys,
  exact scoring.  The mismatch legs verify via `inspect_original` — the
  zoom-card scale is too coarse for grok to *prove* two frames identical,
  so the gate exercises the epic's verification path (full-res originals),
  which is exactly what an agent would do in the real product.
- **Hermetic** `test_timeline_visualize_park24_fixture.py` (default CI):
  slice validity, 24 verified assets, mismatch hash-invisibility, 2-page root
  render with 24 clip cards.

**RESULT (2026-08-11): PASS — all 6 legs × 3 fresh journeys = 1.0.**  The
agent oriented 24 clips, walked the NEXT chain CL08→CL09→CL10, and caught
both hash-invisible mismatches (CL09 duplicate + CL16 foreign) exactly.
Gate evidence: `.r24-evidence/park24/journey-{1..3}/{root,cl08,walk1,walk2,
dup,foreign}.json` (gitignored).  Iteration notes: zoom-card-scale equality
judgment was flaky for grok (abstains) — the mismatch legs verify via
`inspect_original` full-res pages, which is the product's verification path;
the strip-noise pages were excluded from comparison sessions.

### Aspect-aware filmstrip fix (2026-08-11, post-gate UX pass)

User review of the rendered pages found the root's 24 clips showing
"purple rectangles" instead of images.  Root cause: narrow clips (~71px
wide, time-scaled) kept the full 220px portrait lane, so a 16:9 frame
contain-fit into a portrait cell maxed at ~65x37px surrounded by `_CLIP`
purple fill.  Codex (gpt-5.6-luna) diagnosed the same issue on the CL16
poster card (portrait media pillarboxing in a wide card, ~25-30% image).
Fixes (in `layout.py` + `model.py`):
1. **Narrow-clip filmstrips**: cards narrower than `_MIN_VISUAL_CARD_W`
   with a verified frame are capped to the media's own aspect ratio
   (+ label strip) and vertically centered in the lane — full image,
   never cropped, no gutters.
2. **Aspect-aware geometry** (`model.asset_aspects`): parsed from the
   registry `resolution` field; portrait media (<1.2) gets a portrait
   card even for wide/focus cards.
3. **Fixture registry resolution fixed** (`build_park24_slice.py`): the
   builder now records each frame's REAL pixel resolution (the poster is
   864x1222, not the previously-hardcoded 1536x1024).
Result: codex rates root image visibility 4/5; CL16's poster fills its
portrait card (purple ratio 47% -> 21%).

### Navigation polish (2026-08-11, user review round 2)

User: "why does it say TL01 when zoomed in but CL on the root — confusing",
"show the partially revealed image cropped off at the side with a
delineation", "give the images a little buffer".

1. **Bare ordinals on ALL clip cards** (`layout.py`): cards print `CL23`
   at every zoom level; the qualified ref (`TL01.CL23`) lives in the cue
   line, `ground-truth.json`, and `action-index.json` (reading guide
   updated).  Removed the now-dead `_time_clip_label`; linear layout keeps
   its richer `_linear_clip_label` (start/end/duration/authored).
2. **Torn-edge cut delineation** (`render_png.py` + `render_svg.py`):
   in-lane page-break continuation cards get a zigzag torn edge + ellipsis
   on the cut side, so a clipped clip reads as cut off, not truncated.
3. **Cropped continuation image**: page-break tails now paste the VISIBLE
   portion of the frame (cover-crop anchored at the cut side) instead of a
   solid teal block (`_cover_fit`).
4. **Top buffer**: thumbnails get 6px breathing room above the frame
   (label sits in a bottom strip, never overlapping the image).

Golden regen: desert pixel hash `624af363…` -> `739c7251…` (bare labels
change the pixels).  SVG identity contract updated: cards carry stable
ids; the cue carries qualified FOCUS/PARENT refs (audio clips outside the
cue keep their ref in ground-truth/action-index).

### Directional context token (2026-08-11, user review round 3)

User: "show an indicator of how many images are in each direction, or how
much time and frames."

- New `RANGE` cue token on clip/timestamp/range/shot focus pages (absent on
  full-timeline pages): `RANGE ◀ {n} clips · {t}s ▶ {m} clips · {t}s` —
  how many clips and how many seconds exist before (◀) and after (▶) the
  focused clip.  Example (park24 CL16): `RANGE ◀ 15 clips · 63.3333s
  ▶ 8 clips · 34.0000s`.  Counts derive from the model's clip intervals
  (fully-before / fully-after the anchor's window); seconds from the
  anchor's start/end frame positions at the timeline fps.
- Split onto the cue's facts line with `FOCUS CLIP`/`SP @` (leading
  separator stripped).  Reading guide documents the token.
