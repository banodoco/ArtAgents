# Brief — Durable Timeline Visualization

## Outcome

Deliver a stable `astrid timelines visualize` command backed by a reusable
`rendering.timeline_visualize` executor. A VLM-capable Astrid agent must be able
to descend coherently from project overview to timeline, pinned shot or range,
clip context, exact original source media, timestamp, and text/transcript
evidence through time-scaled and readable linear views. The numbered evidence
pack uses matching PNG, SVG, JSON, and Markdown artifacts, and every view
declares snapshot-safe next actions.

The result must be tested iteratively against real and synthetic timelines
until an unfamiliar VLM can parse its structure reliably without source-file
access or follow-up.

The detailed architecture and visual grammar are locked in
[`../decisions/timeline-visualization-plan.md`](../decisions/timeline-visualization-plan.md).
Use that document as the primary design input rather than redesigning the
feature from scratch.

## North Star

A VLM-capable Astrid agent should be able to run one stable command and
understand a project's temporal structure, spatial layering, grouping, and
visual progression through an evidence pack designed specifically for machine
vision, without mutating the source timeline or relying on ad-hoc inspection
commands.

The end state must preserve both proportional timing truth and readable
sequence truth; keep visual and textual explanations aligned through shared
models; expose transitions, effects, overlaps, groups, audio, layer order, and
missing assets; produce deterministic offline project-owned artifacts; and
use stable ids across image and text; distinguish authored captions, mapped
speech, and uninspected text baked into pixels; and let the agent inspect the
verified full-resolution original without mistaking a thumbnail or derived
card for it. Clarity must be proven through repeated image-only VLM
comprehension tests rather than assumed from file generation.

## Scope

### In

1. Add the discoverable executor `rendering.timeline_visualize`.
2. Add the thin managed-project command `astrid timelines visualize`.
3. Support these cold-start and drill-down scopes:
   - every non-tombstoned timeline in a project;
   - one named or default timeline;
   - one pinned shot within one resolved timeline;
   - one closed-open time range;
   - one clip with all intersecting layers, optional symmetric context, and
     previous/next same-track neighbors;
   - one canonical asset and every timeline use;
   - one exact timestamp with an active-layer stack and ±3-second context;
   - one authored text clip, source transcript segment, or mapped timeline
     speech occurrence when explicit provenance exists.
4. Support `time-scaled`, `linear`, and `both` layouts.
5. Represent:
   - track lanes and actual compositor order;
   - clip type, timing, duration, source trim, and speed;
   - thumbnails and missing assets;
   - transitions, effects, animations, gaps, and overlaps;
   - pinned-shot membership;
   - visual and audio tracks;
   - scope truncation and page continuation;
   - snapshot lineage, parent/child/sibling relations, and exact executable
     next actions;
   - source asset role, resolution, integrity, and verified original path;
   - transcript source timing, mapped timeline timing, speakers, trim/speed,
     repeated-source occurrences, and authored-caption separation.
6. Emit:
   - numbered overview and scope PNGs;
   - paginated time-scaled and/or linear PNG and SVG views;
   - best-effort boundary filmstrip with explicit source/approximation state;
   - timestamp active-stack image when applicable;
   - generic visual `reading-guide.md`;
   - concise factual `structure.md`;
   - versioned `ground-truth.json`;
   - `view-map.json` with page bounds, object boxes, visible/omitted labels,
     lane/z order, and continuation links;
   - `action-index.json` with qualified display ids, reversible relations, and
     authoritative `argv` arrays;
   - `asset-index.json` with canonical ids, roles, consumers, dimensions,
     duration, integrity, content hash, and original-media actions;
   - `transcript-index.json` separating source segments (`TS`) from mapped
     timeline speech occurrences (`SP`);
   - `diagnostics.json`;
   - the normal universal result manifest, containing exact agent reading order
     and primary entrypoints.
   The manifest, ground truth, view map, action index, asset index, transcript
   index, diagnostics, and generic reading guide are mandatory core outputs.
   `--format` filters only PNG, SVG, and factual `structure.md`.
7. Add project-owned run behavior, compact agent-oriented result pointers, pack
   metadata, capability documentation, and generated capability-index updates.
8. Add focused model, geometry, output, and CLI tests.
9. Run a live render/inspect/revise loop with schema-constrained, image-only
   VLM comprehension questions.

### Out

- any human-facing dashboard or interactive editor;
- replacing Reigh's interactive editor;
- mutating timeline events, assets, or final-output manifests;
- automatically rendering a final composited video;
- remote-only/Supabase visualization without a local readable projection;
- a persistent watch server;
- an audience-mode switch;
- waveforms in the first release;
- OCR or filename-based transcript guessing;
- remote media fetching or implicit refresh from a frozen view;
- a generic asset-management browser;
- unrelated refactors of the rendering pipeline or event-sourcing system.

## Locked decisions

1. **Capability shape:** build one new rendering executor plus a thin timeline
   CLI façade. Do not implement the feature as an oversized CLI-only command or
   expand `timeline_storyboard` into a god executor.
2. **Invocation boundary:** the CLI resolves managed project state and invokes
   the executor through `astrid.sdk.invoke`; it must not import the executor's
   `run.py` directly.
3. **Managed sources:** the executor accepts repeatable `timeline_source`
   directory inputs. SDK callers supply list-valued inputs, which the existing
   runner expands to repeatable flags. Standalone file inputs remain optional.
4. **Read authority:** managed reads go through the normal timeline CRUD path
   so an event-sourced projection is repaired before visualization.
5. **Shared truth:** build a versioned semantic inspection model, then a
   geometry/layout model. PNG and SVG consume the same layout model; Markdown
   and JSON consume the same inspection model.
6. **Time syntax:** accept raw seconds or `[HH:]MM:SS[.fff]`. Ranges use
   `START..END` and are closed-open.
7. **Shot semantics:** shot scope resolves one
   `pinnedShotGroups[].shotId`, emphasizes its members, and retains every
   other-track clip intersecting the shot bounds.
8. **Layout semantics:**
   - time-scaled width encodes real duration and alignment;
   - linear width is deliberately non-proportional and always prints
     timestamps, duration, gaps, and overlaps;
   - every linear page explicitly states that widths are not time-scaled.
9. **Project semantics:** render an index plus independent timeline subviews;
   unrelated timelines never share one time axis.
10. **Agent evidence contract:** this is an agent-only surface, with no
    `--audience` switch. PNG is the primary VLM artifact. Stable ids must link
    every visual object to `ground-truth.json`, `structure.md`,
    `view-map.json`, and diagnostics; the generic `reading-guide.md` documents
    only id grammar and lookup procedure. Every page has an explicit reading
    order, embedded legend, scope, time bounds, and large layout-mode label.
    Timelines, tracks, shots, groups, clips, transitions, effects, animations,
    warnings, pages, and frame samples all receive distinct deterministic id
    prefixes. Project outputs use globally unambiguous numbered filenames for
    every per-timeline subview.
11. **One follow-up operation:** after a root view, every generated navigation
    action uses `astrid timelines visualize --from-view <manifest> --focus
    <focus-ref>`. Object refs are timeline-qualified (`TL01.CL03`); arbitrary
    frozen timestamps use `TL01@00:12.000`. Display ids are illegal without
    `--from-view`, and actions store argument arrays, not only shell strings.
12. **Snapshot semantics:** a root locks event head/version/hash, assembly and
    registry hashes, transcript hashes, asset hashes, and the stable id map.
    Children read that frozen normalized snapshot, inherit ids, and never
    silently observe current state. `refresh_root` creates a new lineage.
13. **Source media semantics:** the verified original local image or media file
    is the primary resource. Derived cards and filmstrip samples are labeled
    as such. Changed, missing, remote-uncached, unsupported, and thumbnail-only
    sources remain explicit and are never silently substituted.
14. **Transcript semantics:** map only explicitly linked transcripts. Preserve
    segment timing and speakers when present; emit word timing only if the
    linked data actually contains it. One source segment may produce multiple
    mapped occurrences. Authored captions, mapped speech, and uninspected
    baked-in text are distinct evidence types.
15. **Filmstrip semantics:** one scope-level filmstrip, independent of layout.
    Default `auto` uses rendered sampling when an explicit rendered video is
    supplied and otherwise uses asset sampling labeled as a source
    approximation.
16. **Rendering dependencies:** use Pillow and raw deterministic SVG. Do not
    introduce a browser, frontend, or web-framework dependency.
17. **Output ownership:** normal managed runs create new immutable outputs.
    Do not overwrite an earlier preview in place.
18. **No v1 watch daemon:** fast reruns plus manifest entrypoints are
    sufficient.

## Open questions for the planner

Resolve these during planning without changing the North Star:

1. What is the cleanest exact shared-module location for duration and
   asset-resolution helpers used by both `timeline_storyboard` and
   `timeline_visualize`, given current pack conventions?
2. Should the thin CLI handler live in `timeline_output.py` or a new focused
   module while preserving the existing `timeline.py` façade seams?
3. Does `rendering.timeline_visualize` require an entry in
   `output_result_exemptions.json`, or can it conform without one?
4. Which existing project-run/result fields are the stable way for the CLI to
   print the created run id and output paths after `astrid.sdk.invoke`?
5. Which pagination constants should be configuration versus stable defaults
   after testing the real fixture matrix while preserving the locked VLM
   density and typography floors?
6. Which existing transcript schema fields survive current normalization, and
   where must segment-level support be the explicit floor until word-level
   data is demonstrably preserved?

Do not reopen the executor-plus-CLI architecture, the two-model design, or the
scope/layout semantics unless code evidence proves one is impossible.

## Constraints

- Preserve all pre-existing dirty and untracked work. Never reset, checkout,
  delete, or overwrite unrelated changes.
- In particular, treat the current uncommitted
  `rendering.timeline_storyboard` capability and tests as implementation
  baseline, not disposable scratch work.
- Generated media and visualization outputs belong under managed `runs/` or
  another ignored output directory.
- The visualizer is offline and read-only. It must not need credentials or
  network access.
- Missing assets produce visible placeholders and warnings, not crashes.
- Empty timelines produce clear empty-state artifacts.
- Raster pages default to a standard 1920×1080 canvas; density changes trigger
  pagination rather than arbitrarily larger images.
- Track height never drops below 80 px; raster body text never drops below
  24 px; critical labels target at least 32 px; time ticks stay at least 60 px
  apart.
- Overview panels target 6–12 focal objects, use redundant label/shape/pattern
  encodings, and never require hover or interaction to recover facts.
- Dense timelines paginate rather than becoming unreadably small.
- Vertical lane bands share the same ruler/window and all-track index; active
  stacks paginate after 12 layers.
- Filmstrips deduplicate samples at one output frame, preserve first/last,
  select at most 36 candidates with deterministic temporal coverage, and show
  at most 12 frames per page.
- Same-input outputs must be deterministic in the pinned Astrid runtime.
  Across supported Pillow/platform versions, test decoded PNG pixels and
  dimensions rather than raw compressed bytes.
- Timeline and registry inputs must remain byte-identical after every run.
- Every durable JSON machine contract—manifest, ground truth, view map, action
  index, asset index, transcript index, and diagnostics—has an integer
  `schema_version`.
- Drill-down must preserve the root's hashes and id map. A changed current
  asset or timeline never contaminates the frozen child view.
- Original local images remain inspectable at full resolution through exact
  paths and hashes; credential-bearing remote URL query strings never appear
  in outputs.

## Touchpoints

Expected additions:

```text
astrid/packs/rendering/timeline_inspection.py
astrid/packs/rendering/executors/timeline_visualize/
tests/packs/rendering/test_timeline_visualize_*.py
tests/core/cli/test_timeline_visualize.py
tests/fixtures/timeline_visualize/
```

Expected modifications:

```text
astrid/packs/rendering/executors/timeline_storyboard/run.py
astrid/packs/rendering/pack.yaml
astrid/packs/rendering/skill/SKILL.md
astrid/packs/_core/skill/SKILL.md
astrid/core/cli/timeline_parser.py
astrid/core/cli/timeline.py
astrid/core/cli/timeline_output.py
astrid/core/contracts/output_result_exemptions.json  # only if required
```

Follow actual code evidence if a narrowly different file boundary is cleaner.
Do not broaden into unrelated package or timeline-runtime restructuring.

## Required implementation sequence

1. Lock fixture questions and the output schema.
2. Implement and test the normalized inspection, asset, transcript, snapshot,
   and navigation models and scope filters.
3. Implement and test the shared geometry/layout model.
4. Render deterministic SVG and validate geometry.
5. Add Pillow PNG and the numbered agent evidence pack from the same layout.
6. Add stable ids, generic reading guide, factual Markdown/JSON, serialized
   view map, action/asset/transcript indexes, diagnostics, bounded automatic
   filmstrip, source inspection, text maps, and reading-order manifest.
7. Add executor metadata and result-manifest behavior.
8. Add the SDK-backed CLI façade, managed project/all-timeline behavior, and
   snapshot-consistent `--from-view`/`--focus` drill-down.
9. Update skills, pack metadata, capability index, and command documentation.
10. Run the live VLM clarity loop and convert every failure into a fixture,
    invariant, or diagnostic before completion.

## Validation fixtures

At minimum:

1. the current managed `desert-plant-growth/plant-growth-storyboard`;
2. visual + caption + effect + audio tracks with overlaps;
3. transitions and effect-layer clips;
4. pinned shot with contextual clips on other tracks;
5. verified full-resolution, changed, missing, relative, remote,
   thumbnail-only, image, video, and audio assets;
6. tiny clips, long gaps, and split clips;
7. a 500-clip dense timeline;
8. transcript trims, speed changes, repeated source use, speakers, authored
   captions, missing provenance, and no-OCR baked-in text;
9. a project with multiple timelines and colliding local ids;
10. a frozen version-7 root inspected after current state advances to version
    8;
11. an empty timeline.

The critical VLM bundles must cover every selection scope, both time-scaled and
linear interpretation, and exact rendered versus approximate source filmstrip
provenance. The agent must explicitly identify that linear widths are not
proportional.

## Done criteria

The epic is done only when:

1. project, timeline, shot, range, clip, asset, timestamp, and text/speech
   scopes all work through the public command;
2. time-scaled and linear views are both legible and explicitly distinct;
3. every required timeline concept is represented or deliberately warned;
4. PNG and SVG agree because they consume the same geometry model;
5. `structure.md` and `ground-truth.json` explain the same selected semantic
   model and use the same stable ids as the images;
6. outputs are deterministic, offline, read-only, and project-owned;
7. source timeline and asset bytes remain unchanged;
8. focused tests pass, followed by relevant broader CLI/rendering tests;
9. `astrid executors inspect rendering.timeline_visualize --json` succeeds;
10. documented example commands work from both an attached session and
    explicit `--project`;
11. an unfamiliar VLM, given only the fixture-declared ordered image bundle and
    generic `reading-guide.md`—not `structure.md` or `ground-truth.json`—passes
    three consecutive independent reads per critical fixture;
12. active stack, layer order, shot membership, and missing-asset answers are
    exact, while the complete rubric scores at least 95%;
13. the locked rubric uses exact ID/order/state comparison, ±0.05-second time
    tolerance, zero for parse failures/abstentions, recorded model/settings and
    hashes, and fresh sessions for each pass;
14. a fresh agent starting only from CLI stdout discovers the manifest and
    relevant pages, then meets the same factual thresholds;
15. `view-map.json` accounts mechanically for every visible primitive,
    printed/omitted label, page bound, lane band, and continuation;
16. format-specific CLI results use explicit `null` plus a reason when a
    requested format omits a PNG/SVG or factual Markdown entrypoint, while the
    core machine bundle is always present;
17. the complete overview → segment → clip → original-media journey works
    using only generated actions, with a reversible path to the exact parent;
18. child views preserve snapshot hashes and stable ids, while `refresh_root`
    creates an explicit new lineage;
19. the verified original is never confused with a thumbnail, source
    approximation, generation reference/output, or rendered sample;
20. transcript source segments and mapped occurrences are provenance-linked,
    trim/speed correct, and visibly distinct from authored captions;
21. every failed comprehension attempt has become a regression fixture,
    invariant, or diagnostic.

## Anti-scope

- Do not rewrite the event log or projection system.
- Do not change timeline mutation semantics.
- Do not add a frontend framework or HTML dashboard.
- Do not require Reigh or a running server.
- Do not add a generalized dashboard framework.
- Do not silently infer that source-asset thumbnails are final composited
  frames.
- Do not guess transcripts from adjacent files or infer baked-in text without
  recorded OCR evidence.
- Do not fetch remote media, expose credential-bearing URLs, or silently
  substitute a lower-quality asset.
- Do not let a child view silently refresh into current project state.
- Do not optimize for human browsing or add an audience toggle.
- Do not declare success because files were emitted; prove clarity with the
  comprehension rubric.
