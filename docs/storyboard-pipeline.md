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
