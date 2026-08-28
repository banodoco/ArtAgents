# Settled-plan critique — lens: kiss-scope (wave 1)

You are an independent plan-settled CRITIC in a megado run. READ-ONLY: do not modify any repository files. Your output: ranked concrete simplifications with plan-section or source evidence, <300 words. Do NOT widen scope, do NOT rewrite the plan, do NOT invent architecture.

## Immutable plan snapshot (v2, sha256/16 8323bcc7f350603a)

# Plan — FFmpeg text rendering extension (v2)

This revises `docs/ffmpeg-text-extension.md` against the code at `c6c505af` and exploration R1 (E1 hang, E2 routing, E3 fonts). The seed plan’s intent is kept; several of its mechanics, and three v1 claims, were wrong.

**What the code actually is**

- Filtergraphs live in `astrid/packs/rendering/backends/ffmpeg/command.py` (`build_filter_graph`), not `run.py`. `run.py` is the protocol/facade adapter: support → argv → `ffmpeg` → probe. There is no section loop; visual media is concat’d on one spine, then `[vout]` is mapped.
- `support.py` fail-closes on `clipType != "media"` (except the existing audio-reactive specialization), on extra visual tracks, on `clip.effects`, and on media `hold`.
- Real slide text is `clipType: "text"` with **`clip.text`** (content, fontSize, color, align, bold, optional fontFamily/italic) and **`clip.params`** (anchor, offsetX, offsetY, maxWidth, textShadow, weight). Fades are **`clip.effects: {fade_in, fade_out}` in seconds**, or a list of objects with those keys. No timeline- or section-level fade exists. Storyboard captions get `0.2/0.2`; the brand wordmark has no effects. Golden example: `examples/hype.timeline.json`.
- Remotion’s default `TimelineComposition` aliases `text` → the `text-card` effect and **drops** `params.anchor` / wrap / shadow. Overlay parity is **`ThreeTimelineComposition`**: Helvetica/Arial stack, wrap, CSS `textShadow`, anchor+offset, no CDN. That is the bar: visibly equivalent slide text, not pixel-identical browser text, and not text-card chrome.
- **Default routing is ffmpeg-first auto-route, not `legacy_hybrid`.** `rendering.render` defaults selector `"remotion"` → policy `("rendering.ffmpeg", "rendering.remotion")` with `auto_route=True` (`service._translate_legacy_selector`). FFmpeg support is tried first; Remotion is the fallback when ffmpeg fail-closes. `legacy_hybrid` is not on the default path (only the unused `legacy_engine.py` calls it). Therefore **declaring `text` in `renderer.yaml` and accepting media+text in `support.py` does flip default `astrid render` / `rendering.render` for those timelines onto ffmpeg.** That is capability-driven routing working as designed, not a planner change. Planner changes remain a non-goal. Done-criteria renders still go through `rendering.ffmpeg` directly as well.
- Pillow is already a dependency (`pillow>=12.2`). fonttools is not. Repo TTF exists only under `timeline_visualize` (PowerGrotesk) — do not couple to that pack. WOFF2 happened to load on this Pillow 12 wheel; that is not a contract. Resolver stays path-based TTF only.

**Settled within this run**

- **Font:** ffmpeg-backend-local resolver, no new subsystem, no woff2, no fonttools, no PowerGrotesk. Ordered TTFs matching the Three.js stack and the `visual_understand` candidate list: `/System/Library/Fonts/Supplemental/Arial.ttf` (+ `Arial Bold.ttf`, space in the filename), then `/Library/Fonts/Arial.ttf` (+ Bold) for pre-10.15 macOS, then `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` (+ `-Bold`) on Linux. Bold / `params.weight >= 600` → Bold face.
- **Missing font is fail-closed, deliberately, against the `load_default()` repo convention.** Debug-label helpers (`visual_understand`, storyboard thumbs, logo grids) fall back to `ImageFont.load_default()` because any readable glyph is enough. This backend paints user-facing video. `load_default()` is a bitmap face, not Arial/Helvetica — a silent face swap that would violate **output parity** and the **silent-fallback** anti-pattern. The closer precedent is `timeline_visualize` (fail-hard `FileNotFoundError`). Support reports a reason and returns `supported=False`; rasterize raises. Default auto-route then falls through to Remotion, which still can render. Never `load_default()`, never a silent face swap.
- **Fade envelope:** text-overlay alpha only, from **`clip.effects.fade_in` / `fade_out`**. Media clips keep today’s rejection of `effects`. No timeline-level fade object.
- **Parity:** Three/storyboard overlay semantics. Ignore `text.fontFamily` / `italic` (no font catalog). Ignore `clip.x/y/width/height` (unsupported transforms; fail-closed).
- **Overlay termination (E1, load-bearing):** every PNG input is `-loop 1 -t {END:.6f} -i <png>`. `-loop 1 -i` without an input duration **hangs after spine EOF** (killed at 60–120s; truncated mp4, `moov atom not found`). **`-shortest` does not fix it.** Spine is overlay **main**, PNG **secondary** (`[prev][ovK]overlay=…`); inverted wiring inherits the PNG’s infinite 25fps clock. Input `-t` is overlay **END** (absolute timeline time, not `END-AT`), which covers fade-out completion (`st+d = END`). `d=0.000000` is a legal no-op — **always emit both fade filters; no zero-guard branch.** Filtergraph is one argv element (`";".join`); `enable='between(t,…)'` single quotes are ffmpeg’s own quoting and must stay literal in the Python string (no shell). Decimals `:.6f` like the rest of `command.py`. Do not add `-framerate`.

**Explicitly not in this run**

- `legacy_hybrid`, Remotion, `legacy_engine`, storyboard compile, media `hold`, media fades, transitions, `clipType: "text-card"` / other effects, per-frame PIL (`scripts/render_2rp_launch_ffmpeg.py` is the anti-pattern), ffmpeg `drawtext`, a bundled TTF, fonttools/woff2 conversion, `ImageFont.load_default()`, `-shortest`, a fade zero-guard.

---

## Tasklist (covers the ENTIRE agent goal)

1. **Text raster helper — new `astrid/packs/rendering/backends/ffmpeg/text.py`**
   - **Depends on:** nothing.
   - **North Star:** simplest sufficient toolchain (Pillow already in-tree; no drawtext, no font subsystem); fail-closed font resolution (no silent face swap).
   - **Changes:** `_resolve_font_path(bold) -> Path | None` with the candidate list above; `_parse_color`; `_parse_text_shadow` (same CSS form as Three: `offsetX offsetY blur color`); `_wrap_lines` (word wrap to `maxWidth`; `<=0` = one line); `_anchor_origin` (compound `top|middle|bottom` × `left|center|right`, default center; offsets as in `ThreeTimelineComposition`); `_text_window(clip) -> (at, end)` from `hold` else `to` (fail if neither yields positive duration); `rasterize_text_clip(clip, width, height, dest: Path) -> None`.
   - Rasterize onto a **full-canvas RGBA PNG** (position baked in). Overlay later is always `0:0`. Line height `1.2 * fontSize`. Shadow: offset duplicate + optional blur, then fill. No ffmpeg `drawtext`.
   - Missing font → `None` from the resolver; rasterize raises `FileNotFoundError`. Never `ImageFont.load_default()`.
   - Keep this module IO-minimal and unit-testable without ffmpeg.

2. **Support check — `astrid/packs/rendering/backends/ffmpeg/support.py`**
   - **Depends on:** task 1 (font resolver only; do not rasterize at support time).
   - **North Star:** capability-driven routing, fail-closed, yaml/support agreement. This is the switch that flips default auto-route for media+text onto ffmpeg.
   - **Changes:**
     - Accept `clipType == "text"` on a visual track. Require `text.content` non-empty string; parse/validate `hold`/`to` duration; allow `params` keys `{anchor, offsetX, offsetY, maxWidth, textShadow, weight}` only (unknown param → reject); allow `effects` only as fade map `{fade_in?, fade_out?}` (number ≥ 0) or a list of such objects — any other effect key stays rejected. Carve text fades out of the generic `_EFFECT_KEYS` rejection; media clips still reject all `effects` (including `fade_in`). `text-card` and every other non-media type stay rejected.
     - Visual-media spine unchanged: **exactly one visual track that carries media clips**, gapless, no overlap, media still needs `from`/`to` (not `hold`). Extra visual tracks are allowed **iff they contain only `text` clips** (hype’s `brand` / caption tracks). Empty extra visual tracks reject. Text may overlap media in time (overlays, not concat members).
     - Text on an audio track, text with `asset`, text with x/y/width/height/crop/transition/opacity≠1/speed≠1: reject.
     - If any text clip is present, resolve a font path; missing font → reason, `supported=False`. Set report features: `media_only: False`, `text_overlay: True`, `fade_envelope: <any text fade > 0>`, and force `whole_media` / `stream_copy` false (cannot copy while overlaying).
     - Keep `media_only: True` (and current stream-copy logic) for media-only requests.
   - Retarget the existing fail-closed case `unknown_clip_kind` (today it sets `clipType: "text"`).

3. **Filtergraph overlays — `astrid/packs/rendering/backends/ffmpeg/command.py`**
   - **Depends on:** task 2 (so `validate_ffmpeg_media_timeline` / `structural_reasons` no longer explode on text).
   - **North Star:** simplest sufficient toolchain; no hang; no silent fallback. E1 hang fix is mandatory.
   - **Changes:** `RenderCommandInputs` gains an optional `text_overlays: tuple[TextOverlaySpec, ...]` (`path`, `at`, `end`, `fade_in`, `fade_out`). Pure: still no file writes.
     - Visual concat inputs and asset `-i` list: **`clipType == "media"` only** (today every visual-track clip is treated as media and demands an `asset` — that would break the moment support lets text through). Same filter for audio-track collection (defense in depth).
     - When `text_overlays` is non-empty, **never** take the stream-copy branch (`copy_video_input` stays `None`) so a `[vout]` spine always exists to overlay onto.
     - After asset `-i`s, append each overlay as **`-loop 1 -t {END:.6f} -i {png}`** (PNG inputs last). Then after `[vout]` concat, for overlay input index `N`:
       ```
       [N:v]format=rgba,fade=t=in:st=AT:d=FADE_IN:alpha=1,fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1[ovK]
       [prev][ovK]overlay=0:0:enable='between(t,AT,END)':format=auto[next]
       ```
       Always emit both fade filters (`d=0.000000` is a legal no-op). Last label stays `[vout]`. `{AT,END,FADE_*}:.6f`.
     - **Do not** use `-shortest`. **Do not** omit `-t`. **Do not** put the PNG on the overlay main side. **Do not** use `-t {END-AT}` — fade `st=` values are absolute on a stream that starts at 0.
     - Overlay order: track array order, then `at`, then clip index (later overlay on top). Media is the base; all text is above it.
     - `build_render_command` / `from_data` / facade builders take the overlay list from the caller (`run.py`). Do not rasterize here.

4. **Render wiring — `astrid/packs/rendering/backends/ffmpeg/run.py`**
   - **Depends on:** tasks 1 and 3.
   - **North Star:** no silent Remotion fallback; provenance already records `engine: "ffmpeg"`.
   - **Changes:** In `_protocol_render` and `_render_ffmpeg_media_to_path`, after support succeeds: if text clips exist, `TemporaryDirectory` for PNGs, rasterize each, pass specs into the command builder, run ffmpeg **before** the temp dir is gone. Disable stream-copy whenever overlays exist (defense in depth vs support features). Keep existing provenance. Do not change audio-reactive specialization.

5. **Declare capabilities — `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`**
   - **Depends on:** tasks 2–4 landing in the same batch (North Star: never declare what is not implemented; never widen yaml while support lags).
   - **Changes:**
     ```yaml
     clip_types: [media, text]
     features:
       media_only: false
       text_overlay: true
       fade_envelope: true
       stream_copy: true
       sequential_audio: true
     ```
     `stream_copy: true` remains a capability (media-only requests still copy); support features stay request-sensitive. Update the one-line `description` so it is not “media-only”.

6. **Tests — `tests/packs/rendering/test_ffmpeg_support.py`, `test_ffmpeg_backend.py`, new `test_ffmpeg_text.py`**
   - **Depends on:** tasks 1–5.
   - **North Star:** yaml / support / command / reality agree; hang is tested in argv, not discovered in CI.
   - **Conventions:** same fixtures as existing ffmpeg tests (`_timeline`, fake probes, no real ffmpeg except the live smoke). Rasterize tests that need a real TTF call the resolver and `pytest.skip` if it returns `None` — do not bundle a font, do not add a CI font package step.
   - **Must update:**
     - `test_ffmpeg_backend.py`: `clip_types == ["media"]` → `["media", "text"]`.
     - `test_support_fails_closed_for_every_unsupported_semantic` `unknown_clip_kind`: use `text-card` (or another non-text non-media type), **not** `text`.
     - Keep `test_support_rejects_non_media_timeline` (`text-card`) as effect rejection.
   - **Add:**
     - support accepts one visual media + one/N text overlays (same track, and extra text-only visual tracks).
     - support still rejects: text-only (no visual media), `text-card`, extra visual **media** track, empty extra visual track, text effects other than fade, unknown params, missing font (patch resolver to `None`), media `effects.fade_in`.
     - `command.py` argv: extra `-loop 1 -t <END> -i`, `overlay=0:0` with spine/prev **before** the overlay input, `enable='between(t,…)'`, **both** fade filters even when `d=0`, stream-copy **not** selected. Assert **no** `-shortest`. Assert `-t` is overlay END, not duration.
     - rasterize unit tests: wrap, bottom-center / top-right anchors, shadow parse, empty content refused.
     - existing media-only command/support tests still pass (no overlay inputs, stream-copy still available).
   - `tests/core/rendering/test_cli.py` (`"clip_types: media" in text`) still holds as a prefix of `clip_types: media, text`. Do not touch planner tests or `legacy_hybrid`. Do not add a `service.py` auto-route test; support-accepts-media+text is the evidence the default ffmpeg-first policy will pick this backend.

7. **Live smoke (done-criterion 5)**
   - **Depends on:** task 6.
   - **Command (authoritative, host-run once):**
     ```bash
     python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q
     ```
   - Minimal timeline: one `from`/`to` visual media clip (tiny generated H264 or the suite’s real-ffmpeg fixture pattern from `test_ffmpeg_finalizer.py` / compositor), one `clipType: "text"` with `hold`, `params.anchor`, `effects.fade_in/fade_out`, optional audio. Invoke `rendering.ffmpeg` support+render **directly** (protocol `run.main` or `ffmpeg.render`). Assert: `supported is True`, output exists, ffprobe has video and a **finite duration** (hang regression: unterminated `-loop 1` yields timeout / `moov atom not found`), and a sampled frame is not a blank plate (luma/alpha or a small PNG overlay checksum — not pixel-match to Remotion).
   - **Not** the 76-clip intro storyboard: b-roll there uses media `hold` and still images, both pre-existing ffmpeg refusals.
   - `pytest-timeout` is 120s suite-wide; that is a backstop, not the fix. Termination must come from input `-t`.

8. **Docs — `docs/ffmpeg-text-extension.md` only**
   - **Depends on:** tasks 1–7 (claims must match shipped behavior).
   - Correct: filtergraph is `command.py`; fades are `clip.effects`; font is system Arial/DejaVu TTF, fail-closed; overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END`; default `rendering.render` is ffmpeg-first auto-route, so media+text that pass support now render on ffmpeg (Remotion remains the fallback when ffmpeg fail-closes: text-card, media hold, extra visual media, missing font, etc.); `legacy_hybrid` is unused on the default path and is unchanged; intro storyboard is not the smoke target.
   - Do **not** claim the hybrid planner still intercepts text, and do **not** claim yaml/support are “not enough” to change default routing — v1 was wrong about that.
   - Do not edit planner/Remotion docs.

**Batch / commit order:** 1→2→3→4+5 together (yaml never leads implementation) → 6 → 7 → 8. One backend-local batch is fine; do not split yaml from support/run.

**Validation (agent goal):**
- `python -m pytest tests/packs/rendering/ -x -q`
- live smoke above
- `git diff c6c505af..HEAD -- astrid/packs/rendering/backends/ffmpeg/` for oracle

---

## Additional areas to explore

None. E1 closed quoting, decimal formatting, termination, wiring, and the `d=0` no-op. E2 closed default routing (`legacy_hybrid` is not the default; no production `complex_renderers` override; `layer_stack` is qualified-id-only). E3 closed font filenames, Pillow TTF load, and the fail-closed vs `load_default()` tension. Media `hold` / still-image duration remains out of this run.

---

## Open questions

None that block execution. Seed-plan boundaries are resolved: system TTF (Arial/DejaVu, fail-closed), text-only fade envelopes, Three/storyboard overlay parity. Default auto-route of media+text onto ffmpeg is **satisfied** by tasks 2 and 5; it is not a planner change and is not “knowingly unsatisfied.” `legacy_hybrid` still classifies non-media as complex — that path is unused by default and stays a non-goal.

---

## North Star check

This plan advances **simplest sufficient toolchain** (one ffmpeg binary + Pillow already in-tree; no Chrome/webpack/CDN/font subsystem/drawtext/zero-guard/`-shortest`) and **offline by default**. **Capability-driven routing** is honored: `renderer.yaml`, `support.py`, and the filtergraph update together and stay fail-closed (`text-card`, media effects, media hold, missing fonts, extra visual media). Because the default selector is already ffmpeg-first auto-route, that agreement **does** change what `astrid render` uses for media+text — that is the North Star, not a lie. **Output parity** is slide-style overlay (anchor, wrap, shadow, clip fade), not Remotion text-card chrome.

Named anti-patterns, rejected:
- **Routing lies / yaml–support lag:** yaml lands in the same batch as support+command+run; `text` is not declared until the overlay path exists; missing font is `supported=False`, not a claim.
- **Speculative layers:** no font catalog, no planner change, no second overlay mechanism, no `-framerate`/`-shortest`/zero-guard branches that empirics showed are unnecessary.
- **Silent fallbacks:** no Remotion fallback inside the ffmpeg backend; provenance stays `engine: "ffmpeg"`; no `load_default()` face swap. When ffmpeg cannot render, auto-route to Remotion is the existing, recorded fallback — not a hidden swap.
- **Scope creep:** no transitions, no media fades, no media `hold`, no shared font service, no storyboard/planner/Remotion edits.

---

## Effort estimate

About one focused implementation day: one new ~150-line helper, support carve-outs, overlay chain in the existing concat graph with a verified `-t` cap, yaml+tests+one live ffmpeg smoke. No planner/Remotion work. The hang fix is a few argv tokens, not extra architecture.

HUGE-RUN: no


## North Star (complete)

# North Star — Astrid rendering

## Desirable end state
Astrid renders timelines with the simplest toolchain that produces correct output. FFmpeg — one binary, no Chrome, no webpack, no npm tree, no CDN — is the default engine; heavier engines (Remotion) are used only where they genuinely earn their complexity. Engine choice is invisible to the user except as speed and reliability.

## Enduring principles
- **Simplest sufficient toolchain.** Prefer the fewest moving parts that produce correct, good-looking output.
- **Capability-driven routing.** A backend declares what it supports; the router prefers the cheapest capable backend. Support checks are fail-closed and evidence-based — they never claim more than the backend implements.
- **Output parity.** Switching engines must not visibly regress what the user sees: text layout, fonts, position, timing, fades.
- **Offline and fast by default.** Network/CDN dependencies at render time are liabilities, not features.

## Anti-patterns to avoid
- Declaring a capability the backend doesn't implement (routing lies), or implementing without declaring.
- Widening `renderer.yaml` capabilities while `support.py` semantics lag (or vice versa) — the two must agree.
- Speculative abstraction layers, parallel mechanisms where one exists, config surfaces nothing reads.
- Silent fallbacks that hide which engine actually rendered a video.
- Scope creep: this run is about text rendering in the FFmpeg backend — not transitions, not media effects, not a new font management subsystem.


## Agent goal (complete, frozen)

# Agent goal — FFmpeg text rendering extension (megado run, 2026-08-28)

Advances [North Star](./northstar.md): moves text rendering from the Chrome/webpack/CDN Remotion path into the single-binary FFmpeg path, directly serving "simplest sufficient toolchain" and "offline and fast by default", bounded by "output parity" and the capability/support-check agreement principle.

## Objective
Implement `docs/ffmpeg-text-extension.md` (committed at base SHA `c6c505af`) in this worktree so that timelines containing **media + text clips** render end-to-end through the `rendering.ffmpeg` backend, with Remotion unchanged as the fallback for complex segments.

## Authoritative inputs
- `docs/ffmpeg-text-extension.md` @ `46f1aff0` — the seed plan
- Base code state @ `c6c505af` (custody: `./custody.md`)
- User run declaration (below)

## In scope
1. `astrid/packs/rendering/backends/ffmpeg/renderer.yaml` — declare `text` clip type, `media_only: false`, `text_overlay: true`, `fade_envelope: true`.
2. `astrid/packs/rendering/backends/ffmpeg/run.py` — text clip handling: PIL rasterization to transparent PNG (font, size, color, weight, alignment, position/anchor, maxWidth wrap, textShadow), overlay chaining in ONE filtergraph per section, timing via `enable='between(t,start,end)'`.
3. Fade envelope (`effects.fade_in`/`fade_out`) applied to text overlay alpha.
4. `astrid/packs/rendering/backends/ffmpeg/support.py` — return `supported` for media+text timelines the backend can actually render; stay fail-closed otherwise.
5. Tests covering the new behavior; docs update if behavior/claims change.

## Non-goals
- Transitions between media clips; media fade envelopes beyond what the seed plan's fade-envelope step requires.
- Changes to `rendering.remotion`, the `legacy_hybrid` planner, or any other backend/pack.
- A new cross-backend font-management subsystem (font sourcing stays an ffmpeg-backend-local concern).
- Storyboard compile pipeline changes.

## Settled decisions
- Model declaration (user-pinned 2026-08-28, restated, not asked again): **Grok 4.6** = planner/revision/tasklist/oracle/`[XHARD]` (the judgment slots); **GLM 5.3 Flash** (`openrouter:z-ai/glm-5.3-flash` via hermes launcher) = sense-checkers/explorers/normal executors. No switches without user approval.
- The seed plan doc is the starting plan; it is revised through the megado loop, not rewritten from scratch.
- Worktree/branch per custody.md; never `main`.

## Open boundaries (planner resolves within scope)
- Font sourcing: system fonts vs bundled TTF; PIL cannot load `woff2` directly (fonttools conversion or bundled TTF needed).
- Whether "fade envelope" extends to media clips or is text-overlay-only (seed plan wording covers text overlay alpha).
- Exact wrap/shadow fidelity expectations vs Remotion output (parity bar: visibly equivalent for slide-style text, not pixel-identical browser text).

## Authorization boundaries
- Mutate this worktree only. Commit on `megado/oracle-run-ffmpeg-text` after each passing batch.
- Push at finish: explicit refspec `HEAD:megado/oracle-run-ffmpeg-text` → origin. Never main, never deploy/promote.

## Done criteria (all required)
1. A media+text timeline renders through `rendering.ffmpeg`: text visible, positioned per anchor/offset, timed, faded per envelope; output plays.
2. `support.py` accepts media+text timelines the backend renders, and remains fail-closed for unsupported features.
3. `renderer.yaml` capabilities match implemented reality (North Star: no routing lies).
4. `python -m pytest tests/packs/rendering/ -x -q` passes; no pre-existing test regressions in touched surfaces.
5. A short live render smoke test (real ffmpeg invocation on a minimal media+text timeline) succeeds.
6. Docs touched only where behavior changed (e.g. the seed plan's claims now match reality).

## Final validation commands
- `python -m pytest tests/packs/rendering/ -x -q` (authoritative suite run once by host)
- Live smoke render of a minimal media+text timeline via the ffmpeg backend (command finalized in tasklist)
- `git diff c6c505af..HEAD -- astrid/packs/rendering/backends/ffmpeg/` reviewed by oracle

## Sync/promotion policy
- Commit per batch checkpoint; push branch at completion; no merge to main, no deploy. Stop conditions: `blocked` / `failed` / `undetermined` / `retryable` / `escalate` per megado skill — stop and escalate rather than silently widen scope.


## Exploration evidence (groundwork + E1/E2/E3)

# Planner groundwork (v1) — schema, examples, Remotion parity, fades

Extracted from grok-4.6 planning run (see receipts/planner-v1.md). Lines 114-193 of raw output.
## How yaml / `support.py` are## 1. Exact text-clip JSON schema

Canonical Python types: `TextClipData` + `TimelineEffect` in `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle/astrid/core/timeline/banodoco_schema.py`. Zod lives in `@banodoco/timeline-schema` (not in-tree). Validator: `clipType=="text"` requires `text` object with string `content` (`validators/timeline.py:253-268`).

**Clip (allowed keys)** `_CLIP_ALLOWED` (`banodoco_schema.py:354-361`): `id`, `at`, `track`, `clipType`, `asset`, `from`/`to`/`hold`/`speed`, `volume`, `x`/`y`/`width`/`height`, crops, `opacity`, **`params`**, **`text`**, `entrance`/`exit`/`continuous`/`transition`, **`effects`**, plus provenance fields.

**`clip.text` (`TextClipData`, all optional except `content` when `clipType` is `text`)** — `banodoco_schema.py:213-220`:

| field | type |
|---|---|
| `content` | `str` (required) |
| `fontFamily` | `str` |
| `fontSize` | `float` |
| `color` | `str` |
| `align` | `"left" \| "center" \| "right"` |
| `bold` | `bool` |
| `italic` | `bool` |

Full-fixture text keys asserted as exactly those seven (`tests/test_schema_contract.py:103-107`). **No** `weight`/`anchor`/`offset*`/`maxWidth`/`textShadow` on `text`.

**`clip.params` (layout; not in `TextClipData`)** — used by storyboard compiler + Three.js: `anchor`, `offsetX`, `offsetY`, `maxWidth`, `textShadow` (CSS string), `weight` (number). Three.js accepts **only** those params (`ThreeTimelineComposition.tsx:41-45`, `docs/reference/threejs-renderer.md:100-101`).

**`clipType: "text-card"`** is a different shape: copy lives in **`params`**, not `clip.text` (`hype.timeline.full.json:160-176`). Registry aliases `text` → `text-card` (`scripts/gen_effect_registry.py:274-277`).

**`clip.params` vs `clip.text`:** structured captions use **`text` for type, `params` for layout**. Effect clips put args in `params`. For Remotion `clipType:"text"`, `resolveParams` **passes `clip.text` as the effect params and drops `clip.params`** (`docs/reference/timeline-composition-v0.0.6/lib/effect-params.ts:3-7`).

---

## 2. Real examples (committed)

From `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle/examples/hype.timeline.json` (golden small fixture):

**Text clip** (`49:102`):
```json
{"id":"brand_wordmark","at":0.0,"track":"brand","clipType":"text","hold":10.0,
 "text":{"content":"ASTRID","fontSize":28,"color":"#ffffff","align":"right","bold":true},
 "params":{"anchor":"top-right","offsetX":64,"offsetY":48,"textShadow":"0 2px 10px rgba(0,0,0,0.75)"}}
```
Caption sibling `cap_search` also has `effects: {fade_in:0.25, fade_out:0.25}` + `params.anchor/offsetY/maxWidth/textShadow`.

**Media clip** (`40:47`):
```json
{"id":"src_open","at":0.0,"track":"v1","clipType":"media","asset":"main","to":6.0,"from":2.0}
```

Full fixture adds `fontFamily:"IBM Plex Sans"` + `italic` (`examples/hype.timeline.full.json:133-148`).

---

## 3. Intro storyboard (76 / 50 / 177.53s)

- **Authored input:** `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle/storyboards/astrid-intro.storyboard.json` (sections with `vo.text` + image/audio paths — **not** compiled timeline clips).
- **Compiler:** `scripts/build_storyboard.py` (docstring L6-17). Compiled `timeline.json` is **not committed**; golden test rebuilds it (`tests/test_compiler_golden.py:8-11,172-199`).
- Frozen styles (`build_storyboard.py:99-116,340-401`):
  - captions: `text={content: vo.text, fontSize:30, color:"#ffffff", align:"center", bold:false}`, `params={anchor:"bottom-center", offsetY:56, weight:500, maxWidth:1500, textShadow:"0 1px 4px rgba(0,0,0,0.95)"}`, `effects={fade_in:0.2, fade_out:0.2}`
  - brand: `ASTRID`, `align:"right"`, `bold:true`, `params={anchor:"top-right", offsetX:48, offsetY:40, textShadow:...}` — **no fontFamily**.

---

## 4. How Remotion actually paints text (parity)

Two compositions (`remotion/src/Root.tsx:78-89`):

**A. Default `TimelineComposition`** (`@banodoco/timeline-composition` v0.0.6, snapshot in `docs/reference/timeline-composition-v0.0.6/`):
- `clipType:"text"` → `text-card` (`effects.generated.ts:23-26`).
- Component: `astrid/packs/rendering/elements/effects/text-card/component.tsx`.
- CSS: `fontFamily` = `text.fontFamily` else `theme.visual.type.families.body` else **`Chillax, Inter, Arial, sans-serif`**; `fontWeight` 700/400 (or 600 with bounds); `textAlign`; `whiteSpace: pre-wrap` (full-frame) or **`nowrap`** (if `clip.x/y/width/height`).
- **Ignores** `params.anchor/offset/maxWidth/textShadow/weight`.
- Fade is **`theme.motion.fadeMs` (default 450ms)**, not `clip.effects` (`component.tsx:86-93`). Media clips do use `clip.effects` via `useFadeOpacity` (`lib/fade.ts:27-50`).

**B. `ThreeTimelineComposition`** (canvas 2D, `remotion/src/ThreeTimelineComposition.tsx:224-317`):
- Font: **`"Helvetica Neue", Helvetica, Arial, sans-serif`** — **no Google Fonts**, no `text.fontFamily`.
- Wrap on `params.maxWidth`; shadow via `params.textShadow`; weight from `params.weight` or `text.bold`; anchor+offsets as documented. **No fade.**

**Fonts:** `remotion/src/fonts.ts` loads **Google Fonts** Inter / Sixtyfour / JetBrainsMono via `@remotion/google-fonts` (network). Theme `ados-paris-2026` ships **local** Chillax `.otf` + `Pilowlava.woff2` (`examples/themes/ados-paris-2026/fonts/`). Real committed clips almost never set `fontFamily` (only full hype fixture: IBM Plex Sans). Cut pipeline uses `"Inter, system-ui, sans-serif"` (`video_editing/executors/cut/timeline_build.py:37`).

---

## 5. Fade envelope



## E1 findings — ffmpeg overlay/fade on this machine

**1. Version:** `ffmpeg 7.1.1` (homebrew `7.1.1_3`, clang 17, arm64, `libx264` enabled).

**2. Working filter — exit 0, output exactly 3.000000s** (PNG appended LAST; spine = overlay main):
```
-i base.mp4 -loop 1 -t 3 -i ov.png -filter_complex "[1:v]format=rgba,fade=t=in:st=0.500000:d=0.250000:alpha=1,fade=t=out:st=2.000000:d=0.250000:alpha=1[ov];[0:v][ov]overlay=0:0:enable='between(t,0.500000,2.250000)':format=auto[v]" -map "[v]"
```

**3. Frame checks** (outA vs base, overlay region 160×160, mean-abs RGB diff / changed px):
- t=0.1 (outside): (0.9, 0.7, 1.0), 415/25600 px → absent ✓
- t=0.7 (fade-in 80%): (118.2, 55.9, 112.7), 24848/25600 → visible ✓
- t=1.5 (full): (185.9, 76.1, 178.5), 24860/25600 → visible ✓
- t=2.6 (after out): (0.9, 0.6, 1.0) → absent ✓

**4. Quoting:** `command.py:414` emits `";".join(filters)` as ONE argv element; execution is `subprocess.run(command_argv, check=True)` (run.py:124) — no shell. Single quotes in `enable='between(...)'` are ffmpeg's own filtergraph quoting; they must be literal in the Python string and survive untouched (verified via argv-list subprocess, exit 0). Don't shell-escape or double them.

**5. Decimals:** literal `st=0.500000`, `between(t,0.500000,2.250000)` exit 0. `d=0.000000` is a legal no-op (exit 0) — no zero-guard needed.

**Risks (ranked):**
1. **CRITICAL — termination:** `-loop 1 -i png` without an input cap HANGS after spine EOF (killed at 120s/90s; truncated mp4, `moov atom not found`). `-shortest` does **not** fix it (60s timeout, correct wiring). Verified fixes: input `-t <END>` (exit 0, 3.1s — recommended) or branch `trim=duration=<END>,setpts=PTS-STARTPTS` (exit 0, 7.4s, slower).
2. **Input order:** spine must be overlay main, PNG secondary; inverted wiring inherits the PNG's infinite 25fps clock (my mis-wired run: 90 frames → 3.6s duration).
3. PNG defaults 25fps — timings are seconds-based so fades stay correct, but `-framerate <spine fps>` is cheap hygiene.
4. Input `-t` must cover fade-out completion (`st+d ≤ -t`), else the fade never fires.

Scratch files in `/tmp/e1` only; repo untouched.
0


## E2 findings — routing + direct-invocation reality

**Q1 — no production config sets those keys.** Repo-wide grep (yaml/json/toml/py/docs, tests excluded): `simple_renderers`/`complex_renderers`/`renderers` exist only in the planner's allowlist + defaults (`planners/legacy_hybrid/run.py:63-73,418-434`) and tests (`test_legacy_hybrid.py:183,446`; `test_renderer_parity.py:419-422`). Runtime `backend_config` producers: facade `_legacy_backend_config` (`executors/render/run.py:64-95` — remotion namespace + `legacy_hybrid.theme_path` only), CLI `--backend-config` (`run.py:347-351,413`), attached passthrough (`core/rendering/attached.py:54,120-123`), cut/resume (`video_editing/executors/cut/resume.py:176-178` — remotion only). Defaults always win: simple=(ffmpeg,remotion), complex=(remotion,) (`legacy_hybrid/run.py:424-433`).

**Q2 — default path never uses legacy_hybrid. [CONTRADICTS BRIEF]** `rendering.render` defaults selector `"remotion"` (`executors/render/run.py:252,408-412`). `_translate_legacy_selector` (`core/rendering/service.py:167-183`): "remotion" → **renderer** policy `("rendering.ffmpeg","rendering.remotion")` auto_route; "hybrid" → planner legacy_hybrid; "ffmpeg" → strict. For media+text, ffmpeg support fails (media-only manifest `renderer.yaml:14-20`; fail-closed `strict_support` `backends/ffmpeg/run.py:247-272`; text-card rejection `test_legacy_renderer_characterization.py:301-305`) → auto-route to remotion (warning `service.py:730-735`). `layer_stack` (`pack.yaml:55`) is qualified-id-selectable only, never default. legacy_hybrid's only "production" caller is the preserved-unimported `legacy_engine.py:326`; no production module imports it — asserted by `test_production_callers.py:202-207`. Text clips reach Remotion via renderer auto-route, not hybrid complex windows.

**Q3 — protocol.** Manifest command `[python3, run.py]`, ops render/support (`renderer.yaml:6-11`). Transport argv `<cmd> <verb> --request <file> --result <file>`, stdin DEVNULL, env `ASTRID_RENDER_BACKEND` (`transport.py:149,166-189`). Request = JSON file: `{schema_version, timeline_path, output_name, assets_registry_path, window, audio, profile, backend_config, metadata}` — file paths, not contents (`contracts.py:774-786`). Pack-root launcher routes by env/namespace (`packs/rendering/run.py:63-136`). ffmpeg `main` (`run.py:680-721`): `_load_request` → `RenderRequest.from_dict(...).for_backend` (:652-656); workspace = request file's parent (:704); `_protocol_render` re-runs support, fail-closed (:523-535), writes `workspace/outputs/<output_name>` (:556-558); result JSON atomically (:710); failures `_write_failure` kinds protocol/binary_missing/internal, always exit 0 (:700-721).

**Q4 — direct callers exist.** Default "remotion" auto-route invokes rendering.ffmpeg first for media-only timelines (`service.py:171-177,704-737`; provenance `auto_routed` `provenance.py:156-160`); "ffmpeg" strict (`service.py:169-170`). Finalize uses separate `rendering.ffmpeg-finalizer` (`packs/rendering/run.py:35-60`). Cut/resume: remotion only. Tests invoke directly (`test_ffmpeg_backend.py`, `test_ffmpeg_finalizer.py`). **Consequence:** adding text support to rendering.ffmpeg flips the *default* auto-route for media+text timelines to ffmpeg (`supports_full_timeline: true`), independent of hybrid.
0


## E3 findings — font availability + PIL reality

**1. Arial filenames (macOS, this machine, Darwin 24.4.0):** `/System/Library/Fonts/Supplemental/` contains `Arial.ttf`, `Arial Bold.ttf` (space, exact), `Arial Italic.ttf`, `Arial Bold Italic.ttf`, `Arial Black.ttf`, `Arial Narrow*`, `Arial Rounded Bold.ttf`, `Arial Unicode.ttf`. Plan's Bold filename confirmed.

**2. Load test:** `python3` = pyenv **3.11.11** (`~/.pyenv/versions/3.11.11`), Pillow **12.3.0** (pyproject allows `>=12.2,<13`). `ImageFont.truetype(..., 30)` → OK: `('Arial','Regular')` and `('Arial','Bold')`.

**3. Suite env:** pytest pinned `9.0.2` + `pytest-timeout` (suite-wide `timeout=120`, `timeout_method="signal"`), `testpaths = ["tests", "scripts/migrations"]`. No `.python-version`, no repo `.venv`; CI (`ci.yml`) pins **3.11** (`m4-gate`/`m8-installed` matrices add 3.12; `m8` also runs `macos-latest`; `bridge-latency` 3.12; `timeline-vlm-gate` 3.14). **No font/DejaVu setup step anywhere in CI or Makefile** — Linux tests run with whatever the `ubuntu-latest` image ships ([INFERENCE: dejavu-core present, since existing path-based lookups pass there]).

**4. woff2 — premise disproven empirically:** `ImageFont.truetype('examples/themes/ados-paris-2026/fonts/Pilowlava.woff2', 30)` **loaded successfully** → `('Pilowlava','Regular')`. WOFF2 support depends on the bundled FreeType having brotli — present in this Pillow 12 wheel, but not guaranteed on all builds; the resolver targets TTF paths only, so this is moot. **fonttools: not a declared dependency** (checked pyproject deps — absent) though importable in this env transitively; resolver needs none (path-based only). Verified bundled-TTF precedent loads: `PowerGrotesk-Regular.ttf` → `('Power Grotesk','Regular')`.

**5. Existing references the resolver must stay consistent with:**
- `astrid/packs/rendering/understanding/executors/visual_understanding/run.py:198-208` — exact precedent: candidate list `/System/Library/Fonts/Supplemental/Arial Bold.ttf`, `/Library/Fonts/Arial Bold.ttf`, `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`, then `load_default()`.
- `astrid/packs/rendering/executors/timeline_storyboard/run.py:385-390` — bare-name `DejaVuSans-Bold.ttf` + `load_default()` fallback.
- `astrid/packs/rendering/executors/timeline_visualize/render_png.py:72-89` — repo-bundled TTF, docstring says "no system-font lookup", raises `FileNotFoundError` (fail-hard, not fallback) — closest to the plan's fail-closed posture; `packs/**/*.ttf` ships in the wheel (`pyproject.toml:132`).
- `astrid/packs/rendering/executors/video_editing/orchestrators/{animate_image,logo_ideas,vary_grid}/run.py` — hardcoded Supplemental Arial paths + `load_default()` fallback.
- `tests/core/test_style_scope.py:44` — "Arial" as theme family name (CSS-level only, no path).
- `remotion` components use CSS stacks (`'Chillax, Inter, Arial, sans-serif'`); no Python-side overlap.

**Risks:** (a) DejaVu exists on this Mac only as user-installed fonts in `~/Library/Fonts/` — macOS has no system DejaVu, so the Linux path never resolves here (fine; Arial is primary); (b) pre-10.15 macOS kept Arial in `/Library/Fonts/` — keep that fallback candidate as `visual_understanding` already does; (c) existing repo convention is `load_default()` fallback, not raise — plan's fail-closed differs; align deliberately, don't silently diverge.
0


## Your lens

KISS/scope: can the outcome be reached with less work, fewer steps, or fewer handoffs? Is any proposed abstraction, layer, interface, configuration surface, or generalization speculative or unnecessary? Flag overengineering, not just bugs.

If you find nothing material for your lens, say exactly `NO MATERIAL FINDINGS`.
