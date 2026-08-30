# Local-font acceptance receipt

Receipt date: 2026-08-30

The acceptance probe is committed at
`tests/fixtures/remotion-local-font-probe.json`. It renders the exact glyph
probe `Astrid 2RP — Aa 0123` through the Sixtyfour heading family while the
loader simultaneously waits for and checks Sixtyfour, Inter, and JetBrains
Mono. The probe uses no media assets, so a successful non-black text frame is
font evidence rather than an incidental source image.

## Checks

- `python3 -m pytest -q tests/test_remotion_local_fonts.py` — PASS (3 tests).
- `npm run typecheck` — PASS.
- `npm run bundle` — PASS.
- `./node_modules/.bin/remotion render src/index.ts TimelineComposition /tmp/astrid-local-font-probe.mp4 --props ../tests/fixtures/remotion-local-font-probe.json --frames=0-29 --log=verbose` — PASS.
- Render receipt: H.264/AAC, 1920×1080, 30 frames, 1.045333 seconds; output SHA-256 `e1696607180aa04079cc0c58b176e058986b960a7b55ece8d9f34cff60c884dd`.
- Verbose render output recorded `Loading Astrid local fonts` cleared for all render tabs and emitted no hosted font request. The frame-15 visual probe rendered the expected Sixtyfour glyphs on a black canvas.

## Offline contract

The focused test rejects `@remotion/google-fonts`, Google Fonts hosts,
`fetch()`, and `XMLHttpRequest` in the loader. The runtime loader constructs
all sources from Remotion `staticFile()` paths, passes the committed glyph
probe to `document.fonts.load()` and `document.fonts.check()`, and invokes
`cancelRender()` on any missing face. This is the fail-closed path: offline
failure cannot silently become a system-font or hosted-font fallback.

The repository's broader `npm run smoke` remains a known pre-existing failure
because its generated-types snapshot omits `derivedFrom`, `media_id`, and
`origin` while the generated source exports them; this font change does not
touch that snapshot or alter the failure.
