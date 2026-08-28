I'll start by reading the full review brief and the megado/oracle skill so the gate is judged against the actual contract, not the truncaThis is a read-only integration review of the full ffmpeg-text run. I’ll inspect the remaining brief, then the live backend, support checks, and tests agExisting completion aI'll inspect the live integration next: capability/support agreement, rasterization, filtergraph, and whether the declared text path actuaThe host suite result is a colleI'll inspect the FFmpeg text-rendering tests, docs, and checkins fromI'll c inspect the6 FFc505afmpeg text- to HEAD, then citerenderiThe suite error is on an untouched pre-existing import. I’ll write a mechanical GLM review brief and, in parallel, read the yaml/support/command/run/text seams myself.The seams look coherent so far. I’ll write the GLM brief and dispatch it, then keep checking support, overlay argv, and both render paths.GLM is running. I’ll keep checking support features, the protocol render path, extra-track rules, and the tests while it works.GLM is still on “Working…”. I’ll check whether the process is actually making tool calls or has wedged.emotion, and whether yaml capabilities actually match `support.py`.I still need the git range, support/renderer flags, and any accidental remotion/hybrid edits.`run.py` dual paths and fade/overlay tests are next — those will show whether timestamps and stream-copy actually match the plan.**ISSUES** — fail-closed support and argv are strong; live proof is luma-only, and several seed-plan features have no pixel/behavioral tests.

**Range** (worktree reflog; no shell/`git diff --stat`): `c6c505af` → `a5fc84f8` (`megado/oracle-run-ffmpeg-text`): B1 raster → B2 support → B3 filtergraph → B4 run+yaml → B5 smoke → B6 `docs/ffmpeg-text-extension.md`. No `checkins/batch-*.md` or `evidence/`. Extra docs: `docs/storyboard-pipeline.md` (pointer only). Other packs: **not proven unchanged**; hybrid/Remotion tests still use `text-card` (`test_legacy_renderer_characterization.py`, `test_service._hybrid_timeline`, `test_ffmpeg_backend._text_timeline`).

**What tests prove**
- **Visible:** raster bbox (`test_rasterize_places_ink_in_anchored_top_right_region`, bottom-center); smoke `mid_high >= plate_high + 40` at t=1.5 (`test_live_media_plus_text_smoke`).
- **Position:** math + PNG bbox only; smoke never samples a region.
- **Timed:** smoke plate 0.5 / mid 1.5 / post 2.6 + ffprobe duration ≤ 4.5s. Window is real ffmpeg (`shutil.which` skip). **Not playability** (no audio stream assert).
- **Fades:** PNG max alpha 255 (not baked). Argv: `fade st=1.0/2.5`, `enable='between(t,1,3)'`, `-t 3.000000` (absolute END), one `-filter_complex`. Smoke does **not** sample fade-in/out.

**Fail-closed (`test_support_fails_closed_for_text_semantics` + media parametrize):** unknown clip (`text-card`), unknown params (`banana`), text on audio, empty content, bad color/shadow, media effects/transitions, extra visual **media** track, missing font (resolver mocked), `from`/`asset`/hold=0. **No** woff2 case (docs only). Overlap fail-closed is **media** only (`structural_reasons` skips non-media). Raster missing-font `FileNotFoundError` untested.

**Flags:** yaml+`test_manifest_registers_static_raw_command_backend`: `media_only: false`, `text_overlay`/`fade_envelope` true. Request features: overlay without fades → `fade_envelope` false + `stream_copy` false; with fades → true.

**Gaps vs seed plan**
- `maxWidth`: wrap helper only; raster caption uses 1500 (no wrap).
- `textShadow`: parse + invalid support; no ink-under-glyph assert.
- `weight`: implemented (`>= 600` bold); **no test**.
- Align/anchor: bbox, not live frame.
- Layering: argv last-on-top + `_text_overlay_specs` track-array order (monkeypatched raster). **No pixel z-order / overlapping text.**

**Wrong overlay timebase:** smoke **would pass** if fades used overlay-local `st=0` while PNG starts at t=0 (full ink at 1.5). Argv `st=1.000000` + `-t END` would catch that. Small timestamp skew inside [1,2] also passes smoke.**ISSUES** — ffmpeg-text slice has real support/command/parity holes. Overlay PTS origin is not the fade bug.

- **Q3 overlay clocks — OK (by construction, fragile).** `-loop 1 -t {end}` (`command.py:450-453`) makes overlay local t start at 0 with duration = absolute END, so `fade=st={at}` (`313-315`) matches timeline seconds. `enable='between(t,at,end)'` (`321-323`) uses **main** PTS; fade uses **overlay** PTS. They coincide only because concat `setpts=PTS-STARTPTS` plus support’s no-gap first visual at 0 (`support.py:432-438`). `-t {end-at}` or `-itsoffset` would break fades. No `-framerate` on the PNG (image2 default 25) vs canvas fps.

- **Fade envelope not fail-closed.** Support parses fades (`support.py:297-298`, `849-857`) but never checks `fade_in+fade_out <= end-at` or `end-fade_out >= at`. `st={end-fade_out}` (`command.py:314-315`) can be `< at` or **negative**. Overlap → wrong alpha, not hang. `d=0` fades always emitted (`command.py:313-315`; `test_ffmpeg_text.py:367-382`). Zero-d fade-in can leave alpha at 0. Overlay `eof_action` default `repeat`; gated by `enable` after END, so hang is unlikely.

- **yaml vs runtime (routing lie).** `renderer.yaml:14-27` always advertises `clip_types:[media,text]`, `media_only:false`, `text_overlay:true`, `fade_envelope:true`, `stream_copy:true`. Support is **request-shaped**: `media_only`/`text_overlay`/`fade_envelope`/`stream_copy` (`support.py:863-873`). Text-only fail-closes (`support.py:429-430`, `command.py:222-223`) despite yaml `text`. Extra visual **media** tracks still rejected (`support.py:405-408`); only extra **text-only** visual tracks pass (`test_ffmpeg_support.py:720-740`). `stream_copy` yaml is not exclusive of `text_overlay`.

- **Layering ≠ Remotion.** Command concats all visual **media** by `at` into one spine, then **all** text on top (`command.py:200-325`). Track array order only ranks text vs text (`run.py:110-114`). Remotion: later visual track on top (`ThreeTimelineComposition.tsx:33-37,382-386`). Text-track-before-media-track: Remotion hides text; ffmpeg still paints it. Same-track text vs media: ffmpeg always text-over-media.

- **Text window vs `to`/visual bounds.** `_text_window` uses `_clip_duration_seconds` (hold else `to-from`) (`text.py:243-257`). Remotion text planes use **hold only**, else `DEFAULT_HOLD_SECONDS=1` (`ThreeTimelineComposition.tsx:352-358`). Support copy “use at with hold or to” (`support.py:285-287`) accepts `to` that Remotion ignores. Text past visual end is not checked (audio is, `support.py:453-456`).

- **Stream-copy + text.** Support `stream_copy` requires `not has_text_overlay` (`858-873`). Command also requires `not inputs.text_overlays` (`280-282`). No run.py path copies with overlays passed. **Hole:** command never reads timeline text; empty `text_overlays` drops text (`command.py:291-325`, `test_ffmpeg_text.py:404-407`) and can copy.

- **Missing `clipType`.** Support: not in `{media,text}` → reject (`support.py:386-388`). Command: `clipType==media` only (`200-206`) — dropped from spine. Service static check treats omitted as `"media"` (`service.py:1014-1016`).

- **Fonts — OK vs seed.** System TTF only, fail-closed (`text.py:67-75,301-307`; `support.py:755-761`). No woff2/bundled. `fontFamily`/`italic` ignored, not rejected.

- **Text-only — fail-closed, undeclared as standalone.** yaml still lists `text` as a clip type.

- **Private `_` imports.** `support.py:28-35`, `run.py:62-66` pull `_parse_fades`/`_text_window`/font/color helpers.

- **Dual run paths.** Same `_text_overlay_specs` (`run.py:81-131,175-188,631-643`). Legacy: `build_render_command_from_data` + in-memory support flag. Protocol: `build_render_command` **re-reads**, re-`support()`, `except: stream_copy_allowed=False` (`command.py:505-524`). `_support_load_failure` omits `text_overlay`/`fade_envelope` (`run.py:347-357`). `command.py:1` still “media-only renderer”.I’ll confirm the fade-filter default empirically so the review cites observed behavior, not just the docs.ISSUES

**1. Zero-duration fade is not a no-op — no-envelope text eases in.** `command.py` always emits both fade filters, including `d=0.000000` when `fade_in`/`fade_out` are 0 (locked in by `test_both_fades_emitted_even_at_zero_duration`). This ffmpeg treats `duration` default 0 as “use `nb_frames` (default 25)”: `ffmpeg -h filter=fade` shows `nb_frames` default 25, min 1; `vf_fade` only switches to time-based fade when `duration != 0`. Empirically, a 30fps overlay with `fade=t=in:st=0:d=0.000000:alpha=1` is fully transparent at t=0, luma 49 at 0.2s, 222 at 0.9s — a ~25-frame fade-in. Support accepts no-envelope text (`test_support_accepts_text_overlay_without_fades`); live smoke only covers 0.2/0.2 mid-window. Instant captions will ease in for ~0.8s. Omit fade filters when the duration is 0; do not emit `d=0`.

**2. Support overclaims fonts.** `text.fontFamily` and `italic` are ignored (`text.py`); support never rejects extra `text.*` keys. Cut always sets `fontFamily: "Inter, system-ui, sans-serif"`. ffmpeg-first auto-route will accept those timelines and paint Arial. That violates fail-closed capability/support agreement.

Otherwise the integration is coherent: yaml/support/run agree on media+text overlay (text-only and extra visual media tracks fail closed), overlay PTS is aligned via `-t END` from t=0, stream-copy is double-vetoed, hang/window smoke is real ffmpeg, and the diff stays inside the ffmpeg backend + tests + seed-plan doc. Finding 1 is the blocker.
