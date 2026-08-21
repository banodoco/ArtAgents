# Timeline visualization plan

## Outcome

Add a durable read-only command:

```bash
astrid timelines visualize [<timeline-slug>] --project <project>
```

It should let a VLM-capable Astrid agent descend through one coherent
inspection hierarchy:

1. a whole-project index across managed timelines;
2. one complete timeline;
3. one pinned shot or explicit time range, including every intersecting track;
4. one clip with temporal neighbors and active contextual layers;
5. one original source asset at full resolution, or exact source-media samples;
6. one timestamp, text clip, or mapped transcript segment.

Each scope can be rendered in a truly time-scaled layout, a non-time-scaled
linear layout with explicit timestamps, or both. The default result is an
agent evidence pack: paginated images optimized for VLM reading, deterministic
SVG geometry, a concise Markdown structural explanation, a short visual
reading guide, and versioned JSON ground truth. Stable object ids tie every
visual mark to the textual model so an agent can move between visual, spatial,
and structural readings without guessing. Every view also carries snapshot-safe
parent, child, sibling, wider-context, source-media, rendered-output, and text
relations so the agent can drill down or climb back up without reconstructing
state.

This is a visualization and inspection capability. It never mutates the
timeline, event log, asset registry, or final-output manifest.

## Why this is a new capability

`rendering.timeline_storyboard` is useful but narrower: it shows the ordered
source images associated with pinned shots. It does not represent track lanes,
duration, overlaps, effects, transitions, or the active stack at a timestamp.

`rendering.render` shows the final temporal result, but video is slow to scan
and does not expose the structural reasons for what appears.

`astrid timelines show/history/diff/audit/preview` expose the event-sourced
timeline textually, but none creates a spatial overview. Note that the existing
`timelines preview` command projects historical JSON at an event; it is not a
visual preview.

The missing unit of work is therefore a new executor,
`rendering.timeline_visualize`, with `astrid timelines visualize` as its
managed-project convenience surface.

## Command contract

### Managed-project surface

```bash
# Default timeline, both layouts, all output formats
astrid timelines visualize --project desert-plant-growth

# One named timeline
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth

# One pinned shot; include every intersecting track for compositional context
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --shot desert-plant-growth

# A timeline window
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --range 00:08..00:16

# Active composition at one instant, with a small surrounding context window
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --at 00:12

# One canonical clip, with all active layers and optional nearby sequence
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --clip plant-frame-2 \
  --context 2 \
  --neighbors 1

# One canonical asset and every clip that uses it
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --asset plant-frame-2

# Snapshot-consistent drill-down from an existing visualization run
astrid timelines visualize \
  --from-view /absolute/path/to/agent-view/manifest.json \
  --focus TL01.CL03

# An arbitrary timestamp inside that same frozen snapshot
astrid timelines visualize \
  --from-view /absolute/path/to/agent-view/manifest.json \
  --focus TL01@00:12.000

# Every non-tombstoned timeline in the project
astrid timelines visualize \
  --project desert-plant-growth \
  --all

# Select one or both geometric readings
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --layout time-scaled

astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --layout linear

astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --layout both
```

Proposed arguments:

| Argument | Meaning |
| --- | --- |
| optional `timeline-slug` | Named timeline; otherwise the project default |
| `--all` | Visualize every non-tombstoned project timeline |
| `--shot ID` | Use one pinned shot's bounds and emphasize its member clips |
| `--range START..END` | Use a closed-open timeline window |
| `--at TIME` | Show the active stack at one timestamp plus nearby context |
| `--clip ID` | Focus one canonical clip and retain every intersecting layer |
| `--asset ID` | Inspect one canonical asset and its timeline uses |
| `--context SECONDS` | Add symmetric time padding to clip focus |
| `--neighbors N` | Include N previous/next clips on the focused clip's track |
| `--from-view MANIFEST` | Continue from one immutable visualization snapshot |
| `--focus FOCUS_REF` | Focus an exposed object id or qualified timestamp |
| `--layout time-scaled\|linear\|both` | Geometry; default `both` |
| `--format png\|svg\|md\|all` | Optional presentation formats; repeatable, default `all` |
| `--filmstrip auto\|off\|assets\|rendered` | Boundary-sampled strip; default `auto` |
| `--rendered-video PATH` | Required only for exact rendered filmstrip sampling |
| `--project SLUG` | Normal explicit project selector |

`--shot`, `--range`, `--at`, `--clip`, `--asset`, and `--all` are mutually
exclusive cold-start selectors. `--from-view` plus `--focus` is mutually
exclusive with those selectors and with explicit project/timeline selection.
`--context` applies to clip, mapped-speech, or timestamp focus; `--neighbors`
applies only to clip or mapped-speech focus.
Display ids are illegal without `--from-view`; generated actions always use
timeline-qualified references such as `TL01.CL03`.
`--shot` is valid only when resolution yields exactly one timeline (a named
timeline or the project default), and it matches
`pinnedShotGroups[].shotId` within that timeline.

Time values use either raw seconds (`12`, `12.5`) or
`[HH:]MM:SS[.fff]` (`00:12`, `01:02:03.250`). Ranges use two time values
separated by `..`; their semantics are closed-open: `[start, end)`.

Timestamp scope uses a deterministic context window of ±3 seconds, clipped to
the timeline bounds. The active-stack panel itself describes the exact
timestamp; the context strip exists only to show nearby entrances and exits.

There is deliberately no audience switch and no interactive viewer. The only
audience is an agent. The command prints the managed run id, manifest path,
mandatory core entrypoints, and available primary image and factual-Markdown
entrypoints in a compact machine-readable summary; presentation entrypoints
omitted by an explicit `--format` selection are `null` with a reason. It uses
normal project-owned executor output rather than overwriting an earlier preview
in place.

The core machine bundle—`manifest.json`, `ground-truth.json`, `view-map.json`,
`action-index.json`, `asset-index.json`, `transcript-index.json`,
`diagnostics.json`, and generic `reading-guide.md`—is always emitted. `--format`
filters only presentation artifacts: PNG, SVG, and factual `structure.md`.
Thus even `--format png` preserves the cross-artifact evidence contract.

## Agent navigation UX

### One operation after the root view

Cold-start selectors answer direct questions. After the first view, the agent
uses one learned operation:

```bash
astrid timelines visualize \
  --from-view /absolute/path/to/agent-view/manifest.json \
  --focus TL01.CL03 \
  --context 2
```

`--focus` accepts timeline (`TL`), shot (`SH`), explicit navigation range
(`RG`), clip (`CL`), asset (`AS`), source transcript segment (`TS`), or mapped
timeline speech occurrence (`SP`) references declared by the parent view. It
also accepts a qualified timestamp locator such as `TL01@00:12.000`, which
creates a timestamp focus inside the same frozen snapshot without inventing an
object id for every possible instant.
Pinned shots remain authored groups. Ungrouped time windows are labeled
`RANGE`, never silently promoted into semantic shots.

The intended descent is:

```text
project index
  → TL01 complete timeline
  → SH02 or RG03 segment
  → CL03 with nearby sequence and every intersecting layer
  → AS02 verified original media
```

Every child preserves actions for its parent, previous/next sibling,
wider/narrower context, source media, rendered evidence, authored text, and
mapped speech. An agent can always climb back to the exact parent snapshot.

### Cues in images, executable actions in data

The visual pages use compact cues only:

```text
CL03 · AS02 · 00:04–00:08
FOCUS · SOURCE · TEXT
```

Long shell commands never compete with timeline content or depend on OCR.
`reading-guide.md` teaches the generic rule: read the qualified id, then use its
entry in `action-index.json`. `structure.md` begins with a breadcrumb and a
short, deterministic "suggested next actions" list.

`action-index.json` is authoritative and stores argument arrays, not only
shell-escaped strings:

```json
{
  "schema_version": 1,
  "TL01.CL03": {
    "canonical_ref": {
      "timeline_ulid": "01K...",
      "kind": "clip",
      "id": "plant-frame-2"
    },
    "relations": {
      "parent": "TL01.RG02",
      "previous": "TL01.CL02",
      "next": "TL01.CL04",
      "timeline_media": ["TL01.AS02"],
      "mapped_speech": []
    },
    "actions": {
      "focus_context": {
        "kind": "visualize",
        "argv": [
          "python3", "-m", "astrid", "timelines", "visualize",
          "--from-view", "/absolute/.../manifest.json",
          "--focus", "TL01.CL03",
          "--context", "2"
        ],
        "result_scope": "clip"
      },
      "inspect_original": {
        "kind": "inspect_media",
        "asset_ref": "TL01.AS02"
      }
    }
  }
}
```

Each action also declares availability, an unavailable reason when applicable,
the expected result scope, and whether it reads snapshot or current state.
Quoted command strings may be included for readability, but `argv` is the
execution contract.

### Snapshot and lineage semantics

A root visualization locks a source snapshot containing:

- project slug and timeline ULID/slug;
- event-log head version, event id, and event hash;
- projected assembly and asset-registry hashes;
- transcript hashes;
- every unique local source-asset content hash;
- visualization creation time.

Every child reads the parent's normalized snapshot and inherits the root id map.
Objects never renumber because a child shows fewer items. Every page prints a
compact breadcrumb and snapshot badge:

```text
SNAPSHOT · TL01 v7 · SNS:a83f…
PROJECT > TL01 > RG02 00:04–00:12 > CL03
```

Drill-down never silently reads a newer timeline. `action-index.json` exposes a
`refresh_root` action that repeats the root query against current state and
creates a new lineage. If current state differs, the old lineage remains valid
and clearly snapshot-bound.

### Segment and clip focus

- Shot focus uses authored pinned-shot bounds and every intersecting track.
- Range focus uses explicit `[start,end)` bounds and continuation markers.
- Timestamp focus uses `TLxx@[HH:]MM:SS[.fff]`, an exact active stack, and a
  default ±3-second context window inside the frozen parent timeline.
- Clip focus uses the clip's exact timeline bounds, every intersecting layer,
  and one compact same-track predecessor/successor band.
- `--context` adds symmetric time padding.
- `--neighbors N` expands to N previous and next same-track clips, then takes
  the union time range and retains every cross-track contributor.
- Previous/next actions use compositor chronology and never guess semantic
  adjacency across unrelated tracks.

The focused view keeps the full breadcrumb, mini-map position within the
parent, and exact narrower/wider actions. This prevents a visually clear detail
page from becoming contextless.

### Full-resolution source inspection

`asset-index.json` records each qualified asset id, canonical registry id,
roles, consuming clips, resolved state, local path or redacted remote identity,
media type, dimensions, duration, content hash, and inspection actions. Asset
roles are explicit and never interchangeable:

- `timeline_media`;
- `generation_reference`;
- `generation_output`;
- `thumbnail_only`;
- `rendered_sample`.

For a verified local still image, asset focus makes the original file—not a
copy or annotated card—the primary media resource:

```json
{
  "primary_media": {
    "path": "/absolute/path/frame-2.png",
    "media_type": "image/png",
    "width": 2048,
    "height": 2048,
    "sha256": "sha256:...",
    "integrity": "verified",
    "preferred_reader": {"modality": "image", "detail": "original"}
  }
}
```

The evidence pack may add an annotated source-usage card, but must label it as
derived and must never substitute it for the original. For video, asset focus
exposes the verified original plus a trim-aware full-resolution source
filmstrip. For audio, it exposes the original plus linked transcript evidence;
waveforms remain out of scope.

Before original inspection, verify the recorded content hash. Changed, missing,
remote-uncached, unsupported, and thumbnail-only sources remain navigable but
receive explicit unavailable states. This offline command never fetches a
remote fallback and never calls a thumbnail or rendered frame the original.
Credential-bearing URL query strings are not copied into visual/text outputs.

### Failure and recovery

Fail before creating a child run when a display id is used without
`--from-view`, the reference is absent or ambiguous, the parent manifest or
core hashes are invalid, or scope flags conflict. Produce a warning evidence
pack—not a fabricated success—when source media changed or disappeared,
transcript provenance is missing, a group member is absent, or extraction is
unsupported.

Every failure prints exactly one recovery action. Never silently select a
similarly named timeline, a newer clip, another asset with the same basename,
an adjacent transcript file, or a lower-quality media fallback.

### Direct executor surface

The executor remains independently discoverable and runnable through the SDK:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "rendering.timeline_visualize",
    project="desert-plant-growth",
    inputs={
        "timeline_source": [
            "projects/desert-plant-growth/timelines/<timeline-ulid>",
        ],
        "layout": "both",
        "formats": ["png", "svg", "md"],
        "scope": "timeline",
    },
)
```

`timeline_source` is repeatable and points to a managed timeline directory,
not merely `assembly.json`. That directory gives the executor the projected
assembly, asset registry, display metadata, and identity without parallel
lists that can become misaligned. The SDK passes one directory for
shot/range/timeline scope and all selected directories for project scope.

For standalone use, allow an explicit `timeline` file plus optional
`assets_registry`; it is mutually exclusive with `timeline_source`.

The executor input contract uses repeatable `timeline_source` and `formats`
arguments. `astrid.sdk.invoke` supplies these as list-valued mapping entries,
for example:

```python
inputs={
    "timeline_source": [str(path_a), str(path_b)],
    "formats": ["png", "svg", "md"],
}
```

The current executor runner expands list values into repeatable command flags,
so project scope does not require duplicate mapping keys or a temporary
manifest file.

## Architecture

```text
event-sourced managed timeline(s)
        │
        │ read/repair projection through timeline CRUD
        ▼
resolved timeline source(s)
        │
        ▼
normalized inspection model
        │
        ├── scope filter: project / timeline / shot / range / clip /
        │                 asset / timestamp / text / speech
        │
        ▼
layout model
  tracks, clips, boxes, labels, ticks, groups, links, diagnostics
        │
        ├── Pillow PNG renderer
        ├── SVG renderer
        ├── agent evidence-pack assembler
        ├── Markdown explainer
        └── JSON explainer
```

There are two deliberately separate intermediate models:

1. **Inspection model:** semantic timeline facts independent of pixels.
2. **Layout model:** exact pages, boxes, labels, visibility decisions, and
   geometry shared by PNG and SVG.

The second model is essential. Rendering each format directly from timeline
JSON would eventually produce three subtly different explanations.

### Ownership boundary

- `rendering.timeline_visualize` owns normalization, layout, thumbnails,
  rendering, evidence-pack assembly, diagnostics, and output manifests.
- `astrid timelines visualize` owns project/session resolution, projection
  repair, timeline selection, argument validation, managed executor invocation,
  and compact result reporting.
- Existing event-sourced timeline code remains authoritative. The visualizer
  reads `assembly.json` only after the normal read path has repaired it from
  `assembly.jsonl` when required.
- The existing storyboard continues to exist as the focused "generation input
  images" view. Shared duration and asset-resolution helpers should be
  extracted rather than copied.

### Likely files

Add:

```text
astrid/packs/rendering/timeline_inspection.py
astrid/packs/rendering/executors/timeline_visualize/
  __init__.py
  executor.yaml
  STAGE.md
  run.py
  src/
    model.py
    scope.py
    navigation.py
    assets.py
    transcripts.py
    layout.py
    thumbnails.py
    render_png.py
    render_svg.py
    render_text.py
    evidence_pack.py
    diagnostics.py

tests/packs/rendering/test_timeline_visualize_model.py
tests/packs/rendering/test_timeline_visualize_layout.py
tests/packs/rendering/test_timeline_visualize_outputs.py
tests/core/cli/test_timeline_visualize.py
tests/fixtures/timeline_visualize/
```

Change:

```text
astrid/packs/rendering/executors/timeline_storyboard/run.py
astrid/packs/rendering/pack.yaml
astrid/packs/rendering/skill/SKILL.md
astrid/packs/_core/skill/SKILL.md             # regenerated capability index
astrid/core/cli/timeline_parser.py
astrid/core/cli/timeline.py
astrid/core/cli/timeline_output.py
astrid/core/contracts/output_result_exemptions.json  # only if still required
```

`rendering/pack.yaml` must add `timeline_visualize` to its declared
`capabilities` list and `rendering.timeline_visualize` to
`agent.normal_entrypoints`; filesystem discovery alone is not sufficient
documentation.

The CLI handler should invoke the executor through `astrid.sdk.invoke`, not
import and call its `run.py` directly. That preserves the normal capability
registry, project run ledger, isolation, and result-manifest behavior.

## Inspection model

The JSON explainer is a stable, versioned artifact rather than a dump of input
JSON. A simplified shape:

```json
{
  "schema_version": 1,
  "project": {"slug": "desert-plant-growth"},
  "scope": {
    "kind": "shot",
    "id": "desert-plant-growth",
    "start": 0.0,
    "end": 16.0
  },
  "timelines": [
    {
      "slug": "plant-growth-storyboard",
      "duration": 16.0,
      "fps": 24,
      "tracks": [],
      "clips": [],
      "pinned_groups": [],
      "transitions": [],
      "active_intervals": [],
      "warnings": []
    }
  ]
}
```

Every timeline, track, shot, explicit range, group, clip, asset, source
transcript segment, mapped speech occurrence, transition, effect, animation,
warning, page, and frame sample gets a short stable display id (`TL01`, `TR01`,
`SH01`, `RG01`, `GR01`, `CL01`, `AS01`, `TS01`, `SP01`, `TX01`, `EF01`,
`AN01`, `WN01`, `PG01`, `FR01`).
The same id appears in PNG/SVG labels, page metadata,
`ground-truth.json`, `structure.md`, `view-map.json`, and diagnostics.
`reading-guide.md` documents the id grammar and lookup procedure without
listing fixture-specific ids. Display ids are
deterministically assigned from canonical object identity and ordering; they
must not change merely because an unrelated output format is disabled.

Normalized clips include:

- stable clip id, track id/index/kind, clip type, asset id and resolved state;
- `start`, `end`, `duration`, source trim and speed;
- text summary, effect ids, animation ids, transition id/duration;
- pinned-group memberships;
- thumbnail source and whether it is an exact rendered sample, source-media
  sample, static image, or placeholder;
- scope clipping (`continues_before`, `continues_after`);
- z-order/layer order as actually used by the compositor.

For shot scope, derive bounds from the pinned group's member clips, emphasize
those members, and retain every clip on every track intersecting those bounds.
Otherwise the view would hide captions, effects, branding, or audio that
contribute to the shot.

For timestamp scope, produce both:

- a vertical active-layer stack ordered by actual compositor order;
- a narrow context strip around the timestamp so the instant is not isolated
  from its entrances and exits.

### Text and transcript model

Keep three evidence classes separate:

1. authored timeline text/caption clips;
2. spoken transcript segments explicitly linked through
   `sources.<asset>.transcript_ref` and cut provenance such as
   `source_ids.segment_ids`;
3. text visibly baked into pixels, which remains `not_inspected` unless a
   separate, recorded OCR result exists.

Never infer a transcript by filename proximity. Segment-level timestamps,
speaker labels, and source text are guaranteed only when present in the linked
transcript artifact. Word-level timing is emitted only when the actual
transcript data preserves words; the visualizer must not promise or fabricate
it.

For a source transcript interval intersecting a clip, map source time into
timeline time with:

```text
timeline_time = clip.at + (source_time - clip.from) / clip.speed
```

Clip the mapped interval to the clip's source window and timeline bounds.
Reusing the same source segment in multiple clips creates one `TS` source
segment and multiple `SP` timeline occurrences. Each `SP` retains the
originating `TS`, `CL`, and `AS` ids, the mapped interval, speaker, text, and
whether the mapping was exact, clipped, or unavailable.

Text pages use distinct `SPEECH`, `CAPTION`, and `OTHER TEXT` lanes. A clip or
range view prints short excerpts and ids; full text remains in
`transcript-index.json` and `structure.md`. Missing transcript evidence is an
explicit state, not an empty transcript and not a reason to hide the media.

## Visual grammar

### Shared grammar

- Time runs left to right.
- Every image has an explicit reading order and panel number.
- Each track is one labeled horizontal lane.
- Visual tracks use compositor order, with an explicit "top layer" marker.
- Audio tracks follow visual tracks and use a distinct tint.
- Clip fill color encodes clip type; border state encodes selection,
  missing assets, or scope truncation.
- Media clips use deterministic thumbnails when there is enough room.
- Text clips show a short content excerpt.
- Effect-layer clips use a translucent patterned block so the media below
  remains visually legible.
- Same-track transitions use a hatched overlap or edge connector labeled with
  transition id and duration.
- Cross-track concurrency is communicated by vertical time alignment, not
  misleading connectors.
- Pinned groups use a labeled bracket/band and member emphasis.
- Missing assets use a red-hatched placeholder and remain present.
- Meaning is never encoded by color alone: type/state also use label, shape,
  border, or pattern.
- Every clip prints its stable id; every major clip or card prints explicit
  in, out, and duration even when width already encodes time.
- Every page includes project/timeline/scope, total duration, layout mode,
  page number, reading arrow, and an embedded legend.
- Every page includes a compact snapshot badge, breadcrumb, and the qualified
  id needed to find executable next actions in `action-index.json`.
- "TIME-SCALED" and "LINEAR — WIDTHS NOT TIME-SCALED" are large, unambiguous
  page labels.
- No required fact depends on hover, click, animation, transparency alone, or
  external context.
- Raster pages use a standard 1920×1080 canvas unless a fixture proves that a
  second documented size is necessary; density is solved with pagination, not
  a larger image that a VLM may silently downsample.

### Time-scaled layout

Horizontal position and width encode real time:

```text
x = left_gutter + (clip.start - window.start) * pixels_per_second
width = clip.duration * pixels_per_second
```

Rules:

- minimum visible clip width: 4 px;
- labels appear inside clips only when their measured bounds fit;
- thumbnails require at least 96 px;
- major ruler ticks remain at least 60 px apart;
- transitions remain at least 8 px or collapse to an edge marker;
- long/dense timelines paginate into explicit time windows rather than
  shrinking tracks or typography into illegibility;
- split clips receive "continues" edges on adjacent pages.

This mode is the truth for duration, gaps, overlaps, synchronization, and
relative pacing.

### Linear non-time-scaled layout

This mode is a schematic sequence view. It sacrifices proportional width to
make every item readable.

- Clips or shot columns receive a readable fixed/minimum width.
- Each card always prints `in → out`, duration, track, and clip type.
- Chronology remains left to right.
- Gaps appear as labeled connectors such as `+2.4s gap`.
- Same-track overlaps appear as labeled connectors such as `0.3s overlap`.
- Cross-track alignment is not implied; timestamps are the authority.
- Pinned shots may become equal-width columns containing their member clips
  and intersecting contextual layers.

This mode is the truth for identity, ordering, grouping, and metadata. It must
be labeled "linear — widths are not time-scaled" on every page.

### Filmstrip

Filmstrips are derived, not silently authoritative:

- `--filmstrip auto`: use rendered sampling when `--rendered-video` is
  provided; otherwise use asset sampling and label it as approximate.
- `--filmstrip assets`: choose deterministic representative frames from the
  active media assets at scope boundaries; label these "source approximation."
- `--filmstrip rendered --rendered-video PATH`: sample the composited video at
  boundaries and midpoints using ffmpeg; label these "rendered output."
- `--filmstrip off`: no filmstrip.

Sampling points are deterministic and listed in `ground-truth.json`. Avoid
hash-random frame selection: a boundary/midpoint policy is easier to explain
and compare across edits.

The filmstrip is layout-independent and produced once per selected scope.
`--layout both` does not duplicate extraction; scaled and linear views link to
the same timestamped strip. Candidate samples include scope edges, meaningful
clip/shot/group boundaries, and interval midpoints; samples within one output
frame are deduplicated. Select at most 36 candidates with deterministic
first/last preservation and stratified temporal coverage, then paginate at 12
frames per 1920×1080 page. `ground-truth.json` records candidate count,
selection policy, selected timestamps, and omitted count.

## Outputs

Default `--layout both --format all`:

```text
agent-view/
  000-project-index.png             # project scope only
  TL01-000-overview.png
  TL01-100-time-scaled-PG001.png
  TL01-100-time-scaled-PG001.svg
  TL01-200-linear-PG001.png
  TL01-200-linear-PG001.svg
  TL01-300-filmstrip-PG001.png       # best-effort, explicitly sourced
  TL01-400-active-stack-PG001.png    # timestamp scope only
  TL01-500-text-map-PG001.png        # when text/speech evidence exists
  TL01-AS02-000-source-card.png      # derived usage card, never the original
  reading-guide.md
  structure.md
  ground-truth.json
  view-map.json
  action-index.json
  asset-index.json
  transcript-index.json
  diagnostics.json
  manifest.json
```

Project scope repeats the `TLxx-*` family for every selected timeline. Filenames
are globally unambiguous within the pack, while `manifest.json.reading_order`
is the authority when categories have multiple pages.

`manifest.json` declares the exact reading order, the primary image for each
scope, page relationships, source hashes, and every artifact. `reading-guide.md`
is intentionally short and generic: it explains the visual grammar, stable-id
lookup, and which page to inspect for each question type. `structure.md` is the
concise factual explanation of the selected scope. `ground-truth.json` is the
versioned inspection model used for exact lookup and evaluation. Neither
factual text artifact is shown to the VLM during visual-comprehension tests.
`view-map.json` serializes the layout model: page id and dimensions, scope/time
bounds, every visible object's stable id and bounding box, lane/z order,
printed labels, omitted labels with reasons, and continuation links. It makes
spatial claims mechanically checkable without asking a VLM to reverse-engineer
pixels.

`action-index.json` is the executable navigation graph.
`asset-index.json` names verified original media and its exact role.
`transcript-index.json` separates source segments from their mapped timeline
occurrences. Original media remains an external verified resource referenced
by absolute path and hash; it is not copied into or silently resized as part of
the evidence pack.

Every durable machine artifact (`manifest.json`, `ground-truth.json`,
`view-map.json`, `action-index.json`, `asset-index.json`,
`transcript-index.json`, and `diagnostics.json`) carries its own integer
`schema_version`.

PNG is the primary VLM inspection surface. SVG is the geometry-verifiable
source and scalable fallback. Markdown and JSON provide structural reasoning
and exact lookup. There is no HTML dashboard in v1.

## Pagination and density

Do not solve density by making everything smaller.

- Track height never drops below 80 px.
- Raster body text never drops below 24 px; titles and critical mode labels
  target 32 px or larger.
- An overview panel targets 6–12 focal objects. Detail pages may contain more
  primitives, but must split before labels or relationships become crowded.
- Choose time page boundaries from major ticks, then shift to a nearby clip or
  shot boundary when possible.
- Use a small overlap between adjacent pages and clearly mark continued clips.
- When tracks exceed one page vertically, split them into lane bands that share
  the same ruler, time window, and compact all-track index; repeat persistent
  context and mark omitted lane ranges.
- Active stacks paginate after 12 layers while preserving compositor order and
  repeating the selected timestamp.
- Project mode renders an index plus one sub-view per timeline; it does not put
  unrelated timelines on one shared time axis.
- Very large PNG/SVG output is split into numbered pages with a small context
  map and explicit previous/next time bounds.

## Implementation phases

### Phase 0 — lock examples and acceptance questions

Create a fixture matrix before renderer code:

- current `desert-plant-growth` timeline;
- multi-track visual + captions + audio;
- transcript trims, speed changes, repeated source use, speakers, and authored
  captions;
- transitions and effect layers;
- pinned group with contextual overlays;
- full-resolution stills plus missing, changed, remote, and thumbnail-only
  assets;
- tiny clips, long gaps, and overlapping clips;
- 500-clip dense timeline;
- multi-timeline project with colliding local clip ids.

For each fixture, define image-only questions an unfamiliar VLM must answer in
one pass, without timeline JSON, source files, crop/zoom tools, or follow-up,
such as:

- What is the total duration?
- Which clip is active at 00:12?
- Which clips overlap?
- What belongs to this pinned shot?
- Which track is the top layer?
- Which asset is missing?
- What is the exact next focus id for this segment?
- Which original image does this clip use?
- Is this wording authored caption text, mapped speech, or uninspected
  baked-in text?

### Phase 1 — normalized inspection model

1. Extract shared clip-duration and asset-resolution behavior from
   `timeline_storyboard`.
2. Normalize tracks, clips, groups, transitions, effects, assets, explicit
   transcript provenance, and mapped speech occurrences.
3. Implement project/timeline/shot/range/clip/asset/timestamp/text scope
   selection.
4. Lock the root snapshot, stable id map, navigation graph, and exact
   source-integrity states.
5. Emit `ground-truth.json`, `action-index.json`, `asset-index.json`,
   `transcript-index.json`, `structure.md`, and `reading-guide.md`.
6. Test source inputs remain byte-identical.

Exit gate: the textual artifacts answer every fixture question correctly.

### Phase 2 — layout engine and SVG

1. Compute pages, rulers, lanes, sub-lanes, clip boxes, group brackets,
   transitions, labels, and diagnostics.
2. Implement both time-scaled and linear geometry.
3. Render deterministic SVG from the shared layout model.
4. Serialize the same layout model as `view-map.json`.
5. Add structural tests for element counts, boxes, timestamps, and clipping.

Exit gate: no geometry invariant fails, `view-map.json` matches the SVG
primitives exactly, and rasterized SVG passes the same machine checks as the
PNG renderer. Subjective clarity is deferred to the explicit VLM gate.

### Phase 3 — PNG and agent evidence pack

1. Render PNG with Pillow from the same layout model.
2. Assemble the numbered agent evidence pack and reading-order manifest.
3. Add best-effort boundary filmstrip extraction, timestamp active-stack
   panels, clip-context pages, source-usage cards, and text-map pages.
4. Expose verified original media as primary external resources without
   copying or resizing it.
5. Write the universal result manifest.

Exit gate: PNG and SVG agree on clip positions, page boundaries, labels, stable
ids, and warnings; the manifest names every page in reading order.

### Phase 4 — durable CLI façade and project scope

1. Add the declarative parser entry.
2. Resolve default/named/all managed timelines.
3. Repair event-sourced projections through the existing read path.
4. Invoke `rendering.timeline_visualize` through the SDK as a managed project
   run.
5. Implement snapshot-consistent `--from-view` plus `--focus`, including
   `--context`, `--neighbors`, and one explicit `refresh_root` action.
6. Validate qualified display ids, hashes, selector conflicts, and exactly one
   recovery action for each preflight failure.
7. Print compact agent-oriented result pointers.
8. Update pack metadata, pack skill, capability index, and `STAGE.md`.

Exit gate: every documented command works from an attached session and with
explicit `--project`.

### Phase 5 — live clarity loop

Run the command repeatedly against real and synthetic fixtures:

```bash
astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --layout both \
  --format all
```

After each iteration:

1. run an end-to-end discovery trial in a fresh agent context, giving the agent
   only the command's stdout result summary; it must find the manifest, follow
   reading order, choose the relevant pages, and answer the query;
2. separately run an image-only trial through the same image-reading interface
   available to Astrid agents, giving the VLM the exact page bundle declared by
   the fixture plus generic `reading-guide.md`, never `structure.md` or
   `ground-truth.json`;
3. collect schema-constrained answers to the fixture questions;
4. compare answers mechanically with `ground-truth.json`;
5. inspect `view-map.json` and `diagnostics.json`;
6. turn every discovery, readability, or scoring failure into an automated
   invariant or fixture;
7. rerender until three consecutive independent reads pass both gates.

Do not add a watch daemon in the first release. Fast repeatable execution plus
the manifest's primary-image pointer is sufficient; a watch mode can follow
only if repeated use shows it is valuable.

## Automated verification

### Model and scope tests

- duration semantics for `hold` and `(to - from) / speed`;
- track order matches compositor order;
- shot scope retains intersecting contextual tracks;
- range truncation flags, clip context/neighbors, and timestamp active stack;
- pinned-group membership and missing members;
- missing, relative, remote, image, video, and audio assets;
- asset roles, content hashes, changed-source state, and original-media
  selection;
- transcript trim/speed mapping, repeated-source occurrences, speaker
  preservation, missing provenance, and separation from authored captions;
- qualified display-id collision handling across project timelines;
- child focus inherits the root id map and frozen source snapshot;
- empty and tombstoned timelines;
- source timeline and registry never change.

### Geometry tests

- every normalized clip has exactly one visible primitive per applicable page;
- no clip violates minimum width;
- labels never intersect another label's reserved box;
- timestamps match the model within 0.01 seconds;
- ticks remain at least 60 px apart;
- transition count and ids match the model;
- pinned brackets span the correct members;
- split clips have matching continuation markers;
- page clip count stays within the density limit.

### Output tests

- repeated renders are byte-identical for JSON, Markdown, and SVG;
- within the pinned Astrid runtime, repeated PNG renders are byte-identical;
- across supported platforms/Pillow versions, compare decoded pixel buffers
  and dimensions rather than compressed PNG bytes;
- SVG element ids are stable and unique;
- PNG dimensions and representative pixels match fixed expectations;
- JSON validates against its schema;
- manifest declares every output and warning;
- manifest reading order resolves to existing files and stable page ids;
- every generated action has an authoritative argument array, qualified focus
  id, availability state, expected result scope, and snapshot/current-state
  declaration;
- navigation relations are reversible and never leave a child without its
  exact parent;
- snapshot lineage and source hashes survive every drill-down unchanged;
- asset and transcript indexes validate independently and agree with ground
  truth;
- every labeled visual object resolves to the same id and facts in
  `ground-truth.json`;
- `structure.md` uses the same stable ids and facts as `ground-truth.json`;
- `view-map.json` accounts for every visible primitive, printed/omitted label,
  page bound, lane band, and continuation link;
- required facts are visible without hover, interaction, or external assets;
- missing assets produce warnings, not crashes;
- direct executor and managed CLI produce equivalent inspection models.

### VLM comprehension tests

- Critical fixture bundles cover every selection scope and both layouts:
  multi-timeline project index; desert-plant full-timeline progression in
  time-scaled and linear views; pinned-shot contextual layers; range
  truncation/continuation; timestamp active-stack order; multi-track
  overlap/transition; missing asset; dense-timeline page navigation; and asset
  versus rendered filmstrip provenance. They also cover the complete
  root-to-source journey, transcript trim/speed/repetition, authored caption
  versus mapped speech, exact original-media selection, and snapshot/current
  distinction.
- Use `understanding.visual_understand` or the canonical image-understanding
  surface available to VLM-capable Astrid agents. Pin and record model id,
  model revision when available, prompt hash, inference settings, and image
  hashes.
- Each fixture declares an exact ordered image bundle. Give the evaluator only
  that bundle and `reading-guide.md`; withhold source timelines,
  `structure.md`, and `ground-truth.json`.
- Require schema-constrained answers:
  `{fixture_id, answers:[{question_id, answer_ids, time_seconds, state,
  confidence, abstain}]}`. Irrelevant fields are `null`, not omitted.
- Compare total duration, active-at-time, overlaps, transition identity,
  pinned-shot membership, layer order, missing assets, and visual progression
  mechanically against `ground-truth.json`.
- Include explicit questions that distinguish proportional time-scaled geometry
  from `LINEAR — WIDTHS NOT TIME-SCALED`, and that classify every filmstrip as
  rendered truth or source approximation.
- Include exact questions for the next focus id, parent id, source asset id,
  evidence type (`caption`, `speech`, or `not_inspected`), and whether a view
  belongs to the root snapshot or current project state.
- ID sets, ordering, and categorical states use exact equality. Numeric times
  tolerate ±0.05 seconds. Parse failures and abstentions score zero; on a
  critical question either is a failed run. Critical factual questions (active
  stack, layer order, shot membership, and missing-asset state) must be exact.
  Noncritical questions are equally weighted and the complete rubric must score
  at least 95%.
- The release gate requires three consecutive independent passing reads on
  every critical fixture, each in a fresh model session with no carried
  context. Any confident contradiction is a failed render, not an evaluator
  exception.
- An end-to-end agent discovery gate starts with only the CLI stdout summary
  and a fixed user question. The agent must resolve the manifest, select pages
  without hidden hints, and meet the same critical/95% thresholds. The curated
  image-only gate remains separate so discovery and visual-grammar failures are
  distinguishable.
- Store prompts, model identity, answers, scores, and source hashes as ignored
  run evidence so failures are reproducible without committing generated
  media.

### CLI tests

- parser help and mutual exclusions;
- default timeline, named timeline, `--all`, shot, range, clip, asset, and
  timestamp;
- `--from-view`/`--focus`, `--context`, `--neighbors`, and qualified ids;
- display id without parent, absent/ambiguous id, invalid core hash,
  conflicting selectors, and exactly one printed recovery action;
- a version-7 root remains version 7 after project state advances to version 8;
- `refresh_root` creates a distinct current-state lineage;
- explicit project and attached-session behavior;
- project-owned run creation;
- projection repair before visualization;
- compact result summary names every mandatory core entrypoint, plus
  primary-image and factual-Markdown entrypoints when present and explicit
  `null`/reason fields when a requested presentation format omits them.

Suggested verification commands:

```bash
python3 -m pytest \
  tests/packs/rendering/test_timeline_visualize_model.py \
  tests/packs/rendering/test_timeline_visualize_layout.py \
  tests/packs/rendering/test_timeline_visualize_outputs.py \
  tests/core/cli/test_timeline_visualize.py -v
```

```python
import astrid.sdk as sdk

print(sdk.get_capability("rendering.timeline_visualize"))
```

```bash
python3 -m astrid timelines audit plant-growth-storyboard \
  --project desert-plant-growth

python3 -m astrid timelines visualize plant-growth-storyboard \
  --project desert-plant-growth \
  --layout both \
  --format all
```

## Acceptance criteria

The feature is complete when:

1. all selection scopes work: project, timeline, shot, range, clip, asset,
   timestamp, and text/speech;
2. time-scaled and linear layouts are visibly and explicitly distinct;
3. tracks, clips, thumbnails, transitions, effects, overlaps, audio, pinned
   groups, and missing assets are represented;
4. PNG and SVG share one geometry model and agree structurally;
5. `ground-truth.json` and `structure.md` explain the same selected scope and
   use the same stable ids as the images; `reading-guide.md` explains how to
   read those images without leaking fixture answers;
6. outputs are deterministic, offline, read-only, and project-owned;
7. the full focused test set passes;
8. an unfamiliar VLM passes the locked image-only rubric three consecutive
   fresh-session times for every critical fixture;
9. critical structural answers are exact and the overall comprehension score
   is at least 95%;
10. a fresh agent starting only from CLI stdout discovers the manifest and
    relevant images, then meets the same factual thresholds;
11. the agent can traverse overview → shot/range → clip context → exact
    original media using only generated actions, then return to the exact
    parent snapshot;
12. transcript segments, mapped speech occurrences, authored captions, and
    uninspected baked-in text remain distinguishable and provenance-linked;
13. no child silently observes newer state, renumbers root ids, substitutes a
    thumbnail for an original, or guesses missing transcript provenance;
14. every failed comprehension attempt becomes a regression fixture,
    invariant, or diagnostic before release.

## Effort and delivery shape

Expected implementation effort is approximately **15–22 focused days**:

- 2–3 days for inspection, asset, transcript, snapshot, and navigation models;
- 3–4 days for layout, pagination, SVG, and text maps;
- 2–3 days for PNG, evidence-pack assembly, filmstrip, and source inspection;
- 2–3 days for the managed CLI, frozen drill-down, and recovery behavior;
- 6–9 days for journey fixtures, VLM evaluation, repeated live iteration, and
  hardening.

This is best executed as a two-milestone epic. Milestone one establishes the
complete visualization and snapshot-safe navigation spine through original
media. Milestone two adds transcript/text mapping and proves the entire journey
through adversarial VLM comprehension and freshness/integrity fixtures. The
second milestone consumes the first milestone's written navigation contract
instead of redesigning it.

## Explicit non-goals for the first release

- any human-facing dashboard or interactive editor;
- replacing Reigh's interactive editor;
- mutating timeline events or final-output records;
- rendering the final composited video automatically;
- remote/Supabase visualization without a locally readable projection;
- a persistent watch server;
- an `--audience` mode switch;
- a generic asset browser or media-management surface;
- OCR or filename-based transcript inference;
- remote media fetching or credentialed URL resolution;
- implicit refresh from a frozen view into current project state;
- waveforms unless real usage shows that duration/volume indicators are
  insufficient.
