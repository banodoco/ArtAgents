# Oracle Batch 4 REWORK — mechanical fact extract (ProRes 4444)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Branch: layer-plan. Commit: 70c5cdee (rework). Parent: 2a2ba6b8.
Read-only. Do not edit files. Cite file:line. <450 words.

HOST-PROBED (treat as fact; do not re-render):
- Remotion 4.0.509 `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png` → .mov, pix_fmt **yuva444p12le**, real alpha.
- Unstamped path must stay h264/yuv420p/.mp4.
- Compositor already treats `pix_fmt startswith yuva` as alpha (compositor/run.py ~345). Zero compositor change was mandated.

## Do this

1. `git diff 2a2ba6b8..70c5cdee --stat` and `--name-only`. List every path. Flag ANY touch of service.py, dispatch, validate_output_name, compositor/run.py, concat finalizer. Also note `.oracle/checkins/batch-4.md` if rewritten.

2. Quote from `astrid/packs/rendering/backends/_shared/__init__.py`:
   - `_timeline_alpha` exact body + what it reads (`metadata.astrid_layer.alpha`?).
   - `_alpha_output_name` exact remap rule.
   - `_remotion_mux_profile` (or equivalent) declared fields when alpha vs unstamped.
   - Any import from `astrid.core`? Y/N + lines.

3. Quote from `astrid/packs/rendering/backends/remotion/run.py`:
   - Exact CLI flags appended when `_timeline_alpha` is true.
   - Theme neutralization: exact assignment (`theme_color["bg"] = "transparent"`?). Which dict is mutated (merged_props theme)?
   - Both output_name remaps (SDK path around :643 and protocol path around :916).
   - Unstamped: confirm flags/profile/output_name unchanged vs parent if possible.

4. Quote from `astrid/packs/rendering/backends/threejs/run.py` the remap + profile. Confirm it does NOT set remotion CLI flags itself. Confirm threejs `<color attach="background">` skip is UNCHANGED in this commit (`git diff 2a2ba6b8..70c5cdee -- remotion/src/ThreeTimelineComposition.tsx` should be empty).

5. Path binding:
   - `service.py` still hardcodes `segment-NNNN.mp4`? Quote.
   - Does the service require `RenderResult.video.path` basename == `request.output_name`? Quote the check. If the backend remaps .mp4→.mov, does the RESULT artifact path stay consistent so compositor/finalizer finds the .mov?
   - How does the compositor/concat finalizer resolve layer paths — from artifact.path, or from request.output_name?
   - `_OUTPUT_NAME_RE` already allows `.mov`? Quote.

6. Tests: list new/changed test names in both backend test files. For the corner-alpha test quote the exact assertion (`corner[3] == 0`?). Does it extract a real frame (ffmpeg/PIL) or only check declared pix_fmt?

7. Theme: find how DOM TimelineComposition parses `theme.visual.color.bg`. Does it accept the string `"transparent"` (CSS), or only hex/#rrggbbaa / rgb()? Quote the composition / color parser. If it would throw or fall back to opaque, say so.

Do not run remotion/pytest. Print-only python ok. Do not implement.

## Report shape

```
SCOPE: clean|dirty — paths; frozen files touched? Y/N
STAMP: how alpha is read
FLAGS: exact argv extras when alpha
PROFILE: declared container/codec/pix_fmt/time_base/audio
THEME: exact assignment + where
THEME-ACCEPT: transparent accepted? Y/N + line
NAMING: remap rule; service still .mp4?; validator allows .mov?
PATH-BIND: result path must == request.output_name? Y/N + how compositor finds the file
SHARED: core import? Y/N
THREEJS-BG-SKIP: unchanged? Y/N
TESTS: name → assert
CORNER: real-pixel? Y/N + assertion
```
