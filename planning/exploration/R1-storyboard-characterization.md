# R1 — timeline_storyboard characterization (frozen baseline)

Recorded 2026-08-11 in worktree `astrid-timeline-vlm` before any epic code.
The storyboard pack is a **frozen baseline**: read-only for the
timeline-visualization epic (it may extract shared helpers later, never mutate
the baseline behavior).

## 1. Test suite status

```
.venv/bin/python -m pytest tests/packs/rendering/test_timeline_storyboard.py -q
8 passed in 6.82s
```

All 8 tests pass. Coverage: reference ordering (`generation.references` with
`asset`/`assetKey`/`id`, `asset:` prefix stripping), Discord `input_media`
ordering through `input_media_10`, shot-id filtering + "pinned shot not found"
error, placeholder/prompt/metadata shots with authored bounds, dangling-clip
and reversed-bounds rejection, contact-sheet PNG determinism + missing-image
placeholder, and `main()` manifest outputs.

## 2. Observable behavior on the desert fixture

Ran `build_storyboard` against the real fixture
(`projects/desert-plant-growth/timelines/01KYPVKMW5STB4W6FE05ED8242/`):

1. **Registry load fails as-is.** `registry.json` carries `sourceId` /
   `sourceVersion` / `resolution` keys that the frozen validator
   (`_ASSET_ENTRY_ALLOWED` in `banodoco_schema.py`) rejects →
   `ValueError: Asset registry.assets['plant-frame-1'] has unknown key
   'sourceId'`. The raw fixture registry is not consumable by any current
   registry consumer.
2. **Zero shots after sanitizing the registry.** The projected
   `assembly.json` (and `assembly.checkpoint.json`) contain **no
   `pinnedShotGroups`**. The storyboard derives everything from
   `pinnedShotGroups`, so it renders the empty body "This timeline has no
   pinned shot groups" (preview.json `shots: []`). The desert fixture's pinned
   shots live only in `manifest.json.final_outputs` (storyboard-png runs), not
   in the timeline assembly.

### Key behavior extracted from run.py (read-only)

- **Input resolution priority** (per shot group, first non-empty wins):
  1. ordered `clip.generation.references` entries (`asset`, `assetKey`, `id`);
  2. Discord `generation.input_media`, `input_media_2..10` (sorted 1..10);
  3. member-clip `asset` for group `mode: "images"`;
  4. `imageClipSnapshot[].assetKey` for group `mode: "video"`.
- **Shot-id policy**: `--shot-id` filters groups; unknown id raises
  `AstridError("pinned shot not found", recovery_command=...)`.
- **Asset resolution**: `file` (absolute, or relative → resolved against the
  **registry's parent dir**), else `url`, else `thumbnailUrl`; entry absent or
  file missing ⇒ `missing: true`; non-image media type ⇒ missing. Broken refs
  stay visible as placeholders (never silently dropped).
- **Remote fallback**: `_is_remote_source` accepts `http/https/data/file`
  schemes; remote sources are clickable in HTML and skipped by the PNG
  contact sheet.
- **Duration semantics** (`_clip_duration`): `hold` wins; else
  `(to - from) / speed` (`from_` checked before `from`); negative → 0. Shot
  bounds = min/max over member clips of `at + duration`. Authored
  `start`/`end` are honored **only** for clip-less placeholder shots, and only
  when `start < end`; dangling `clipIds` never unlock authored bounds.
- **Placeholder detection**: no `asset` on any member clip AND all members are
  non-`media` clipType AND no resolved inputs ⇒ `placeholder: true`.
- Read-only: inputs are never mutated (tests assert byte-identical inputs).

## 3. Implications for the epic

- The epic must **normalize the fixture registry** (drop/reconcile
  `sourceId`/`sourceVersion`/`resolution`) or extend the schema before any
  consumer can read the desert timeline.
- `pinnedShotGroups` is absent from the projected assembly; the epic's
  shot/`--shot` scope needs either a fixture with authored groups or a
  synthetic pinned-shot overlay. Note `projection.py` (frozen, dirty from
  another initiative) already adds `pinnedShotGroups` to
  `_PROJECTED_TOP_ALLOWED`, so a future projection may carry them.
- Shared duration + asset-resolution helpers the epic should extract from
  this pack: `_clip_duration` (hold vs from/to/speed), shot-bounds
  computation, and `_resolved_asset` fallback order (file → url →
  thumbnailUrl) — but read from the frozen source, never copy-diverge.
