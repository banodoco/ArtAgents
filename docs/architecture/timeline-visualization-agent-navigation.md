# Timeline Visualization — Agent Navigation (M1 → M2 handoff)

*Status: M1 complete (R18). Binding input to M2 (R19+). Schema versions cited
from `astrid/packs/rendering/executors/timeline_visualize/schemas/` — every
claim below is grounded in the actual code, not the plan.*
*Source of truth: this document + the schemas + the emitted artifacts of a
real run (see §1 for how to produce one).*

---

## 1. Overview

One command produces everything an agent needs to navigate a frozen timeline
snapshot:

```sh
astrid timelines visualize --project <slug>
```

- **stdout** is exactly one compact JSON object (`sort_keys`, no newline):
  `run_id`, `run_root`, `manifest_path`, `pages`, plus `entrypoints` and
  `formats` summaries. This JSON is the agent's *only* input; it must never be
  derived from repository knowledge.
- **The evidence pack** is the run-owned directory `run_root/agent-view/`
  (the path of `manifest.json` is in stdout). It contains nine mandatory core
  artifacts: `manifest.json`, `ground-truth.json`, `view-map.json`,
  `action-index.json`, `asset-index.json`, `transcript-index.json`,
  `diagnostics.json`, `metric-definitions.json`, `reading-guide.md`, plus
  optional `structure.md`, `PG*.png`, `PG*.svg`, and `filmstrip/*.png`
  (ledger: `pack-hashes.json`).
- **The drill-down operation** is `astrid timelines visualize --from-view
  <manifest> --focus <ref>`: it re-validates the prior pack (containment,
  full hash ledger, schemas, run ownership — `frozen.load_frozen_view`),
  rebuilds the model *exclusively from hashed frozen facts*, and emits a new
  child pack. Children copy the root-lineage substrate byte-for-byte
  (`frozen_objects`, `frozen_timeline`, `frozen_shots`, `frozen_ranges`) and
  the parent's `asset-index.json`/`transcript-index.json` verbatim, and add
  one `parent_view` action on `TL01`.

Fresh-agent journey (proven by `tests/packs/rendering/
test_timeline_visualize_journey.py`, every step using a verbatim action argv):

```
stdout JSON → root manifest → TL01.focus_timestamp (whole-timeline TL focus;
desert has no pinnedShotGroups) → TL01.CL03.focus_context (--context 2) →
TL01.AS03.inspect_original (verified_original) → TL01.parent_view
```

## 2. Implemented schemas (all `schema_version: 1`)

Location: `astrid/packs/rendering/executors/timeline_visualize/schemas/`.
`_defs.json` is shared infrastructure (not an emitted artifact).

| Schema | File | Top-level fields |
|---|---|---|
| manifest | `manifest.json` | `schema_version` (1), `kind` (`timeline_visualize`), `inputs` (`timeline_source`, `from_view`, `focus`, `scope`, `layout`, `formats`), `outputs`, `created`, `warnings`, `run_id` (ULID), `run_root`, `snapshots`, `compositor` (`package`, `version`, `source_snapshot_path`, `registry_default_fingerprint`), `scope`, `layouts`, `page_count`, `reading_order`, `entrypoints` (10 keys incl. `action_index`), `optional_formats`, `companions` |
| ground-truth | `ground-truth.json` | `schema_version`, `snapshots`, `project_slug`, `scope`, `objects` (identity triples), `timelines[]` (`timeline_ref`, `durations` (3 named extents), `tracks`, `clips`, `assets`), `frozen_objects`, `frozen_timeline`, `frozen_shots`, `frozen_ranges`, `timestamps.frozen_at` (sentinel, never SNS) |
| view-map | `view-map.json` | `schema_version`, `snapshots`, `pages[]` (`page_id`, `dimensions`, `layout`, `scope`, `time_bounds`, `object_boxes`, `labels`, `continuation_links`, `reading_order`), `reading_order` |
| action-index | `action-index.json` | `schema_version`, `snapshots`, `entries{ref: {canonical_ref, relations, actions}}` |
| asset-index | `asset-index.json` | `schema_version`, `snapshots`, `assets[]` (`stable_id`, `qualified_ref`, `canonical_ref`, `source_id`, `source_version`, `role`, `integrity_state`, `expected_sha256`, `observed_sha256`, `contained_path`) |
| transcript-index | `transcript-index.json` | `schema_version`, `snapshots`, `sources[]` (TS), `speech_occurrences[]` (SP). **Empty arrays are valid in M1**; M2 fills them without changing the v1 shape |
| diagnostics | `diagnostics.json` | `schema_version`, `snapshots`, `diagnostics[]` (`severity` warning/error, `code` `[A-Z][A-Z0-9_]*`, `message`, `object_ref` nullable) |
| metric-definitions | `metric-definitions.json` | `schema_version` (1), `kind` (`timeline_visualize_metric_definitions`), `compositor_version` (`0.0.6`), `metrics[]` (14 fixed, ordered) |

`snapshots` is byte-identical across every artifact of one pack.

## 3. Display-id grammar

- Qualified refs: `TL01`, `TL01.SH01`, `TL01.RG01`, `TL01.CL03`,
  `TL01.AS03`, `TL01.TS01`, `TL01.SP01` — pattern
  `^TL\d+(\.(SH|RG|CL|AS|TS|SP)\d+)?$` (`_defs.json#/$defs/qualified_ref`).
- Timestamp locators: `TL01@HH:MM:SS.fff` (also `MM:SS[.fff]` accepted as
  input) — `_defs.json#/$defs/timestamp_locator`.
- **Semantic identity** is `(timeline_uuid, kind, authored_id)` — the
  canonical ref. **Lineage-local display identity** is the qualified ref;
  `stable_id` is its suffix (`CL03`). The two are coupled only through the
  pack's identity map; display ordinals are allocated deterministically
  (`navigation.build_identity_map`): `TL01` always the timeline; `CL` in
  compositor clip order; `AS` in sorted registry-key order; `SH` in
  `pinnedShotGroups` order; `RG` minted by `assign_range_ids` in start-time
  order; `TS`/`SP` emitted by M2 transcript attachment (R20).
- **Children never renumber**: scoped emissions filter entries; ordinals are
  never re-allocated (verified by the frozen child copying `frozen_objects`
  byte-for-byte).

## 4. Snapshot fields (SNS)

- SNS preimage (`snapshot_digest.sns_digest`, `SNS_SCHEMA_VERSION=1`):
  canonical JSON (`sort_keys`, `,`/`:` separators, `ensure_ascii`) of exactly:
  `schema_version`, `project_slug`, `timeline_uuid`, `timeline_ulid`,
  `head_version`, `head_last_event_id`, `head_last_hash`, `assembly_sha256`,
  `registry_sha256`, `media_hashes` (sorted), and optionally
  `transcript_sha256`. **Wall-time (`created_at`, `frozen_at`) is excluded**
  and any unknown key is rejected.
- `event_head`: `{version, last_event_id, last_hash}`; version 0 requires
  null tail fields. The event tail of the replayed log is authoritative —
  a stale `assembly.head.json` sidecar cannot change the SNS (R17 matrix
  Area 2).
- `fps`: `assembly.theme_overrides.visual.canvas.fps` (default 30).
- Compositor provenance: `compositor.package` (rendering pack),
  `version` = `COMPOSITOR_VERSION` (`"0.0.6"`), `registry_default_fingerprint`
  = sha256 of the pinned transition defaults (`{cross-fade: 8, fade: 8}`,
  `model._PINNED_TRANSITION_DEFAULTS`); the 12-frame hard fallback
  (`TRANSITION_FALLBACK_FRAMES`) is separate.
- `timestamps.frozen_at` is a fixed sentinel `2026-08-11T00:00:00Z` — never
  the wall clock, never in any preimage.

## 5. Action relations

Each `action-index.json` entry: `canonical_ref`, `relations`, `actions`.

- Relations (v1): `parent` (null at TL01), `previous`, `next` (same-track
  clip ordering), `children`. `parent`/`children` and `previous`/`next` are
  reciprocal; targets outside a scoped emission are reported `null` (never
  dangling). The plan's `timeline_media`/`mapped_speech` relations are NOT
  part of v1 — they await the TS/SP extension points (§10).
- Action kinds: `visualize` (`--from-view --focus` drill-downs) and
  `inspect_media` (`inspect_original`). Every `visualize` action with a
  non-null `focus` carries exactly one `--from-view` and one `--focus`
  (schema-enforced); action `argv` is prefixed `python3 -m astrid` and
  `--from-view` is **pack-relative** (`manifest.json`) so packs relocate.
- Per-entry actions: `TL01` → `focus_timestamp` (whole-timeline midpoint,
  `--context 3`), `refresh_root`; `CL/SH/RG/AS` → `focus_context`
  (`--context 2`); `AS` → `inspect_original` (available only for
  `verified_original`; deterministic `unavailable_reason` otherwise).
- Frozen children add `TL01.parent_view` → `--from-view <parent-manifest>
  --focus <parent scope ref>` — the one follow-up operation returning to the
  exact parent scope identity (kind + ref; context reverts to the 3s
  default).
- `refresh_root` (`reads: "current"`, focus must be `TL01`) is the **sole
  current-state transition**; every other action reads the frozen snapshot.

## 6. CLI examples (real invocations)

```sh
# cold roots — project default timeline; mutually exclusive selectors
astrid timelines visualize --project desert                  # default both layouts, all formats
astrid timelines visualize --project desert --all            # every non-tombstoned timeline
astrid timelines visualize --project desert desert-slug      # by timeline slug
astrid timelines visualize --project desert --shot SH01
astrid timelines visualize --project desert --range 0..13.9  # closed-open window (frame-quantized)
astrid timelines visualize --project desert --at 00:00:08.500
astrid timelines visualize --project desert --clip plant-frame-3 --context 2 --neighbors 1
astrid timelines visualize --project desert --asset plant-frame-3

# presentation
--layout time-scaled|linear|both            # default both
--format png --format svg --format md       # repeatable; default all
--filmstrip auto|off|assets|rendered        # rendered requires --rendered-video PATH

# drill-down (the only navigation form)
astrid timelines visualize --from-view <root>/agent-view/manifest.json --focus TL01.CL03 --context 2

# frozen-lineage transition
astrid timelines visualize --from-view <root>/agent-view/manifest.json --focus TL01 --refresh-root
```

Rules: `--from-view` and `--focus` must be supplied together; neither can be
combined with cold selectors; `--refresh-root` requires `--from-view
--focus TL01`.

## 7. Source-integrity states (exact rules, `resolution.classify_asset` +
`assets.verify_now`)

| State | Rule |
|---|---|
| `verified_original` | expected sha256 recorded AND file present under `project_root/sources` AND `observed == expected` (re-verified right now for sampling) |
| `missing` | contained local path exists but the file is absent (or unreadable) |
| `hash_mismatch` | expected recorded, file present, `observed != expected` |
| `hash_unrecorded` | file present, no expected sha256 recorded (a fresh hash never retroactively verifies) |
| `remote` | reference is a URI / remote ref — never fetched |
| `thumbnail_only` | role derived thumbnail/proxy — no hash required, never substituted |
| `unsupported` | path escapes `sources/` (outside-sources, symlink-escape, no contained path) |

Sampling and original inspection are allowed **only** for `verified_original`
(`assets.guard_sampling`, `assets.verified_source_path`; no fallback, no
fetch).

## 8. Time semantics (from `metric-definitions.json`, compositor v0.0.6)

The five named timeline-level notions map to these metric ids (14 metrics
total; `unit` and `scope` are closed enums):

| Named notion | Metric id(s) | Definition |
|---|---|---|
| authored visual-only | `authored_visual_only_end_seconds` | max over visual-track clips of `authored.start + clip_source_duration` — no speed, no quantization (desert: 13.8667s) |
| frame-quantized visual | `frame_quantized_visual_end_frames` / `_seconds` | max independently rounded visual clip end frame (`Math.round`), seconds = frames/fps (desert: 332fr/13.8333s) |
| all-track composition | `all_track_composition_frames` / `_seconds`, `composition_extent` | `timeline_duration_frames` over EVERY clip (audio, muted, effect-layers included), one-frame floor (desert: 2352fr/98.0s) |
| visual-only span | `frame_quantized_visual_end_*` | the visual half of composition; no separate id exists in v1 (see report) |
| audible span | `audible_extent` | max frame-quantized end across audio-track clips / fps |

Compositor rule citations (`duration.py`): numeric `hold` wins
unconditionally over `from`/`to` (`clip_source_duration`, TS 7–13);
duration divides by raw `speed ?? 1` (`clip_timeline_duration`, TS 15–18);
frames use JS `Math.round` (half toward +∞) with a `max(1, …)` duration floor
(`clip_start_frame`, `clip_end_frame`, TS 3–5, 30–32); composition = max end
over all clips with 1-frame floor (`timeline_duration_frames`, TS 34–41);
transitions resolve explicit frames → rounded seconds → registered default
(8) → 12-frame fallback, ignored when non-positive or exceeding either clip
(`resolve_transition_duration_frames`, transitions.tsx 27–51,
TimelineComposition.tsx 196–200); visual tracks paint in **reverse config
order** (`visual_tracks_paint_order`, tracks.ts 9–14 + TC 314); v0.0.6
transition grouping mounts source `[F, F+Df)`, destination
`[F+Df−T, F+Df−T+Dt)` clipped to composition (model
`_transition_interval_maps`, TC 208–237). Per-scope metrics:
`clip_authored_interval`, `clip_frame_interval`, `clip_mounted_interval`,
`clip_effective_interval` (the transition-clipped presentation), 
`transition_resolved_duration_frames`, `clip_source_duration_seconds`.

## 9. Fixture ids (portable, deterministic)

- Portable slice: `tests/fixtures/timeline_visualize/desert_slice/`
  (event log `assembly.jsonl` v159, uuid
  `ed70ef66-43da-4182-9f14-69361c6c5e10`, ulid
  `01KYPVKMW5STB4W6FE05ED8242`, slug `plant-growth-storyboard`).
- `desert_truth.json` facts: fps 24; authored visual-only 13.8667s;
  frame-quantized visual 332fr / 13.8333s; all-track composition
  2352fr / 98.0s; audio clip `[12, 2352)`; `toccata-fugue` hash_unrecorded;
  no `pinnedShotGroups` (zero shots).
- Compositor parity fixtures `tests/fixtures/timeline_visualize/compositor_parity/`:
  F1 `F1_hold_only`, F2 `F2_from_to_speed`, F3 `F3_hold_speed_interaction`,
  F4 `F4_audio_extends_duration`, F5 `F5_muted_track_not_excluded`,
  F6 `F6_frame_rounding_edge`, F7 `F7_transition_bounds`,
  F8 `F8_z_order`, F9 `F9_speed-zero-rejected`,
  F10 `F10_transition-last-clip-ignored` (+ independent `oracle.py`).
- Deterministic verified media for journey tests: 4×4 RGB PNGs written under
  `project_root/sources/…` with the registry EVENT hashes aligned (see
  `test_timeline_visualize_journey.py::_write_verified_media`).

## 10. M2 interface (what R19+ consumes)

R20 identity rule: `TS` display ordinals remain lineage-local (`TL01.TS01`,
...), while their canonical authored identity is
`transcript:<full transcript_sha256>:segment:<declared-or-positional-id>`.
Changing transcript bytes therefore creates a different TS identity space even
when a fresh root happens to allocate the same display ordinal. An `SP`
canonical identity appends its carrying clip id; every `(TS, clip)` use is a
separate occurrence and reuse never collapses.

1. This document + the eight schemas (v1) as the contract.
2. `transcript-index.json` empty-valid shape: `sources` (TS: stable_id,
   qualified_ref, canonical_ref, asset_ref, transcript_sha256,
   source_segment_id, source_interval, speaker_state, speaker, text,
   word_timing, words) and `speech_occurrences` (SP: + source_ref, clip_ref,
   asset_ref, authored_mapping, effective_mapping) — `authored_mapping`
   preserves source-to-timeline arithmetic before compositor transitions;
   `effective_mapping` records the retimed/clipped presentation.
3. Action-index extension points for TS/SP: relations and actions keyed by
   `TL01.TSxx`/`TL01.SPxx` refs (schema already accepts the pattern; M2 adds
   e.g. text/speech focus actions while keeping v1 shape).
4. `reads: "current"` remains reserved for `refresh_root`; all M2 navigation
   stays snapshot-read-only.
5. Cold `--range` scopes mint RG ids at root creation (e.g. `TL01.RG01`,
   ordered by start time, deterministic per bounds) so RANGE focus is
   navigable through the frozen preflight; see the implemented
   `assign_range_ids` integration in the executor path.
