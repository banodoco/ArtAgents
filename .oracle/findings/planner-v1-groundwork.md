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

