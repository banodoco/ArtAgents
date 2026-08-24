# Replay — external animation pack render 2

Date: 2026-08-23  
Mode: live end-user CLI/SDK journey only; no product code, tests, git state, or prior QA reports inspected.

## Disposable scope

- Projects root: `/tmp/astrid-replay-extra-projects-5C8iOi`
- External pack collection root: `/tmp/astrid-replay-extra-pack-RAw32Q`
- Pack: `/tmp/astrid-replay-extra-pack-RAw32Q/gentle_fade_pack`
- The repository `astrid/packs/local` was not edited.

## Journey and commands

1. Confirmed the documented gateway census with `python3 -m astrid --help`. It exposed the five product families (`projects`, `timelines`, `media`, `tasks`, `runs`), three operational families (`serve`, `doctor`, `backup`), and only the documented nested mounts (`timelines shots`, `media references`). No pack family was added to the gateway.
2. Read the public pack/element/render stage docs. Created the disposable pack with the public scaffold command:

   `PYTHONPATH=/Users/peteromalley/Documents/reigh-workspace/Astrid python3 -m astrid.core.pack.cli new gentle_fade_pack`

   Added one `animations/gentle-fade` element (Remotion adapter) whose public component fades from opacity 0 while translating upward, then reaches full opacity. `python3 -m astrid.core.pack.cli validate ... --warnings` returned `valid`.
3. Verified pack discovery from both configured-root forms:

   - `ASTRID_PACKS_PATH=/tmp/astrid-replay-extra-pack-RAw32Q python3 -m astrid.core.pack.cli list --json` returned `gentle_fade_pack`, `origin=external`, with the disposable root.
   - `python3 -m astrid.core.pack.cli list --json --pack-root /tmp/astrid-replay-extra-pack-RAw32Q` returned the same pack/root.
   - `python3 -m astrid.core.element.cli --pack-root ... inspect animations gentle-fade --json` resolved `animations/gentle-fade`, `pack_id=gentle_fade_pack`, and the component under the disposable root.
4. Created project `gentle-demo` named `Gentle External Pack Demo`, then created/defaulted timeline `title` named `External Gentle Fade Title`. Updated it through `timelines save` to a valid document containing visible text `EXTERNAL GENTLE FADE` and an entrance animation `{type: gentle-fade, duration: 24}`. `timelines show --json` preserved that title and reference.
5. Rendered through the normal project-scoped public SDK path, with `ASTRID_PROJECTS_ROOT` and `ASTRID_PACKS_PATH` set:

   `sdk.invoke("rendering.render", kind="executor", inputs={"timeline": ".../gentle-demo/render-env-only.timeline.json"}, project="gentle-demo")`

   Successful run: `9955982d6cb4e53ad93a8b23a7`. SDK returned `ok=true`, primary `hype.mp4`, and provenance sidecar. The real output was stored in the managed media CAS at:

   - Video: `/tmp/astrid-replay-extra-projects-5C8iOi/.astrid/media/sha256/b5/04/b5047211378d1233679ba0248b57884a770bc6e30e1db712f5d6628ce6a16011`
   - Provenance: `/tmp/astrid-replay-extra-projects-5C8iOi/.astrid/media/sha256/fb/38/fb3883bbc70a4e430c745f8cf506f86f8f9cf486d62782ec7bea77ad884154f4`

## Observations

- `ffprobe` reported a 1920x1080 H.264/AAC output, 90 frames at 30 fps, 3.05 seconds.
- Frame inspection showed the title absent at the start, partially/softly entering during the first frames, and fully visible after the 24-frame entrance window. This is a visible execution difference, not merely metadata.
- Provenance `backend_fragments.rendering.remotion.legacy_v1` recorded:
  - `active_pack_order`: `gentle_fade_pack` with `source_kind=env` and the exact disposable root;
  - `resolved_animation_ids`: `gentle-fade`;
  - `resolved_animations`: `source=pack:gentle_fade_pack`, `source_pack_id=gentle_fade_pack`, `clip_ids=[title_clip]`, and the exact element root;
  - `source_pack_ids`: `gentle_fade_pack` plus the built-in/local text-card element used by the text clip.
- The successful render's output is content-addressed under `.astrid/media`, not a `<project>/runs/` directory. `runs show --evidence` still reported the project-scoped run as succeeded with one succeeded child.

## Deliberate unresolved-element case

Changed only the entrance type to `missing-external-animation` in a new timeline and invoked the same project-scoped path. Run `7dbb6f789eb8f1bb8ca87c3989` failed closed with:

`CapabilityRuntimeError` / `handler_failed`: `rendering.remotion does not support this render request: timeline uses unregistered animation 'missing-external-animation'`.

The SDK returned `ok=false`, `outputs={}`, and no published result. `runs show --evidence` showed one failed child and no evidence/output artifact. A filesystem check of `.astrid/media` showed only the earlier successful video/provenance pair; no missing-animation artifact was added.

## Friction

- The first hand-authored timeline omitted required track `label`; rendering returned a clear schema error. After adding `label`, the next attempt exposed that current timeline schema uses `entrance`/`exit`/`continuous`, not a free-form `animations` clip property. Updating the timeline via the documented `timelines save` CAS path fixed this.
- Supplying both `ASTRID_PACKS_PATH` and SDK `extra_pack_roots` discovers the same external pack twice in provenance. The final successful replay used `ASTRID_PACKS_PATH` alone and recorded one `source_kind=env` entry.
- `doctor --json` was healthy for Python, data paths, SQLite, FKs, and schema; it warned about one orphaned staging directory left by the managed render output.

## Verdict

PASS. Pack CLI discovery and project-scoped SDK rendering honored the same external root; the external animation visibly ran and provenance named the external pack/root/element and involved clip; an unresolved animation failed closed with a typed actionable error and zero new output artifacts; and the root gateway remained the documented eight-family surface (with the two nested mounts).
