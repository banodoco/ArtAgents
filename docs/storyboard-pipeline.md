# Storyboard Compile & Render Pipeline

## Problem

The Astrid intro video was built by hand-editing timeline clips via `build_timeline.py`.
Every content change required re-running the script, which regenerated TTS audio, re-imported
media, and re-saved the kernel timeline. There was no separation between authored content
(what to say, which images to use) and compiled output (kernel clips with CAS locators).

This caused:
- Stale audio when captions were edited but TTS wasn't re-run (hash-bust miss)
- Stale images when the storyboard was edited but the kernel wasn't re-saved
- No way to query "which prompt generated slide 7's image"
- Confusion about which timeline was canonical (main v13? v14? v15?)

## The solution: storyboard JSON → compiler → kernel timeline

```
storyboards/astrid-intro.storyboard.json     (AUTHORED — you edit this)
        ↓ scripts/build_storyboard.py compile
build/storyboard-compiled/{timeline.json, assets.json}   (COMPILED — deterministic)
        ↓ astrid timelines save
Kernel: main config_version N+1              (DURABLE — single authority)
        ↓ astrid timelines render
astrid-intro-pyramid.mp4                     (OUTPUT)
```

## Data model (storyboard v1)

```json
{
  "version": 1,
  "meta": {
    "title": "Astrid Intro",
    "canvas": "1920x1080@30",
    "style": "pixel-terminal",
    "timing": {"default_hold": 3.0}
  },
  "sections": [{
    "id": "idea1_vc",
    "nav": {"tabs": ["1 TOOLS & STRUCTURES", "2 COLLECTIVE KNOWLEDGE"], "active": 0},
    "image": {
      "path": "/abs/path/to/pyramid-art.png",
      "provenance": {"prompt": "...", "generator": "codex-image-generation"}
    },
    "vo": {
      "text": "VibeComfy lets your agent deeply understand workflows...",
      "audio": {"asset": "/abs/path/to/idea1_vc.wav"}
    },
    "provenance": {"prompt": "...", "generator": {...}}
  }]
}
```

### Key rules
- **Authored file**: content + provenance. NEVER receives media_id, content_hash, or resolved paths.
- **Kernel timeline**: compiled output. The single authority for what gets rendered.
- **One-way bridge**: `compile → save → render`. Never write kernel values back into the storyboard.
- **Prompts live in the storyboard** (per-section provenance), not in sidecar files.
- **Variants** (optional): `image.variants[]` + `active_index` when you have A/B alternatives. The intro currently uses `image.path` directly (simplified model).

## Current state

### What works
- `scripts/build_storyboard.py` CLI: `validate` and `compile` subcommands
- `astrid/core/storyboard/loader.py`: `load_storyboard`, `validate_storyboard`, `StoryboardError`
- Compiler emits: timeline.json + assets.json with managed CAS imports
- `--vo-align plan.json` maps section starts to VO segment starts
- Golden parity test: 25 sections → 76 clips / 50 assets / 177.53s ±0.5
- Tracked at `storyboards/astrid-intro.storyboard.json` (committed)
- 25 tests green (`test_storyboard_schema.py` + `test_compiler_golden.py`)

### What's NOT working
- Rendering from the megado worktree fails due to Remotion/Google Fonts environment issues
- Renders from the main checkout work but use the old `build_timeline.py` output, not the storyboard compiler output
- The storyboard compiler's output has been saved to kernel `main` v14/v15 but those renders hit the font error
- The ffmpeg text-rendering extension (see `docs/ffmpeg-text-extension.md`) would eliminate the Remotion dependency

### Path to working end-to-end
1. Fix the font loading issue (see `docs/ffmpeg-text-extension.md`)
2. Compile the storyboard from the main checkout
3. Save to kernel (`main` or a dedicated slug)
4. Render and open

## Usage

```bash
# Validate
python3 scripts/build_storyboard.py validate --story storyboards/astrid-intro.storyboard.json

# Compile (imports managed media, emits timeline + assets)
ASTRID_PROJECTS_ROOT=<root> python3 scripts/build_storyboard.py compile \
  --story storyboards/astrid-intro.storyboard.json \
  --vo-align build/segments/plan.json \
  --project astrid-intro \
  --out build/storyboard-compiled

# Save to kernel
astrid timelines save main --project astrid-intro \
  --config "$(cat build/storyboard-compiled/timeline.json)" \
  --registry "$(cat build/storyboard-compiled/assets.json)" \
  --expected-version <current>

# Render
astrid timelines render main --project astrid-intro --output-name <name>.mp4
```

## Key invariant

The storyboard JSON is an **authored input artifact** (like scripts/prompts — source content
and lineage). It does NOT receive kernel-derived values (media_id, content_hash, resolved
paths). Those live in the kernel timeline and the compiled registry. The kernel is the sole
authority for durable execution state.

## Shots projection & sub-timeline plan

This database (`$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3`) is the **local Reigh database** —
the SQLite authority that replaces Supabase in the local stack. Reigh UI, the worker, and
Astrid all read/write it through the bridge.

### Current state (verified 2026-08-28)

- `shots` and `shot_items` tables exist (shots pack, `astrid/packs/shots/`) but hold **0 rows**.
  The intro's 25 sections live only in the storyboard JSON and the timeline document — never
  projected as shot rows.
- The schema has **no shot↔timeline anchoring**: `shots` is `id, project_id, name, sort_key,
  metadata_json`. No `timeline_id`, no `start_seconds`, no `duration_seconds`.
- Reigh's editor does **not** render nested sub-timelines. `TimelineConfig` is flat
  `clips[]` + optional `pinnedShotGroups[]`; a shot is a *soft grouping* over flat clips
  (`PinnedShotGroup = {shotId, trackId, clipIds, mode, videoAssetKey, imageClipSnapshot}`).
  Shot-scoped generation uses `imageClipSnapshot`; rendering is always flat.

### The model: a shot IS a sub-timeline

**Not** `pinnedShotGroups` — that is Reigh's legacy soft-tag overlay over flat clips, and it
is explicitly rejected as the mechanism here. The design is real nested composition:

1. **Each shot owns its own timeline document.** A `timelines` row per shot whose document is
   the shot's composition (for the intro: broll plate + caption + VO audio for that section).
   Reference stored in `shots.metadata_json` as `{"timeline_document_id": "<timelines.id>"}` —
   data, not an FK, so the plugin law holds.
2. **The parent timeline references shots as composite clips**: a `shot` clip type,
   `{"id": "shot_<slug>", "at": <start>, "track": "broll", "clipType": "shot",
   "params": {"shot_id": "<kernel shot id>"}, "hold": <duration>}`. Placement and duration
   live in the parent document; content lives in the shot's document.
3. **Render-prep expansion**: before a document reaches any renderer, the kernel resolves each
   `shot` clip — fetches the shot's sub-document via its `timeline_document_id`, splices the
   sub-clips into the parent at the shot's `at` window (offset + clamp to `hold`). ffmpeg and
   Remotion see exactly the flat document they see today — **zero renderer changes**.
4. **Editing is scoped**: Reigh's shot detail view edits the shot's own timeline document.
   The parent timeline only carries the `shot` clip. Shot edits never touch the parent.

### Hard constraint: the plugin law

Schema packs may FK only to kernel tables (`projects`, `media`); the only cross-pack currency
is `media_id`. The shots pack "never FK's to or imports the timeline pack"
(`astrid/packs/shots/schema-pack.yaml`). Therefore a `timeline_shots` junction table with an
FK to `timelines` would violate the pack architecture. **Do not add it.** The
shot↔timeline-document association stays in `metadata_json` (open-shaped by design).

### Current state (verified 2026-08-28)

- `shots` and `shot_items` tables exist (shots pack, `astrid/packs/shots/`) but hold **0 rows**.
  The intro's 25 sections live only in the storyboard JSON and the flattened timeline
  document — never projected as shot rows or sub-documents.
- The schema has no shot↔timeline anchoring; `metadata_json` is the open-shaped place for it.
- Reigh's `PinnedShotGroup` exists in the editor but is **not** part of this design.

### Phase A — shot rows + shot sub-timelines + expansion

1. Register shots via `ShotsService` with deterministic idempotency keys
   (`<project>:shot:<slug>`; items `<project>:shot-item:<slug>:image` / `:vo`) — receipt
   idempotency makes retries replay-safe. Metadata carries slug, nav, prompt.
2. Per shot, save a `timelines` row with the section's sub-composition document (3 clips),
   then record `timeline_document_id` in the shot's metadata.
3. Compile the parent timeline as 25 `shot` clips (plus the brand wordmark) instead of 75
   flat clips, each `params.shot_id` pointing at the real kernel shot id.
4. Implement render-prep expansion in the kernel timeline layer; verify the expanded document
   is byte-equivalent (modulo clip ids) to today's flat compile output — the existing golden
   parity test becomes the expansion test.
5. Render through the unchanged ffmpeg/Remotion backends.

### Phase B — Reigh integration

Shot detail view (already exists in `reigh-live-main`) reads/edits the shot's own timeline
document through the bridge; the parent timeline shows `shot` clips as atomic blocks.

### Phase C — true nested render (only if expansion proves insufficient)

Renderer-native compositing: a `shot` clip becomes a render pass with its own canvas/time
window (ffmpeg: render sub-timeline to an intermediate file, then overlay; Remotion:
`<Sequence>` nesting). Enables per-shot effects, resolution, and speed ramps — but is a real
renderer-contract change. Do not start until Phase A is green and a concrete limitation is
hit.
