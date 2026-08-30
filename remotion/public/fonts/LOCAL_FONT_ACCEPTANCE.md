# Local-font acceptance receipt

Receipt date: 2026-08-30

The acceptance probe is committed at
`tests/fixtures/remotion-local-font-probe.json`. It renders the exact glyph
probe `Astrid 2RP — Aa 0123` through the Sixtyfour heading family while the
loader simultaneously waits for and checks Sixtyfour, Inter, and JetBrains
Mono. The probe uses no media assets, so a successful non-black text frame is
font evidence rather than an incidental source image.

## Checks

- `python3 -m pytest -q tests/test_remotion_local_fonts.py` — PASS (4 tests).
- `npm run typecheck` — PASS.
- `npm run bundle` — PASS.
- `sandbox-exec -p '(version 1) (allow default) (deny network-outbound) (allow network-outbound (remote ip "localhost:*"))' ./node_modules/.bin/remotion render src/index.ts TimelineComposition /tmp/astrid-local-font-offline.mp4 --props ../tests/fixtures/remotion-local-font-probe.json --frames=0-29 --log=verbose` — PASS (exit 0; committed network-denial receipt below).
- Offline render receipt: H.264/AAC, 1920×1080, 30 frames, 1.045333 seconds; output SHA-256 `64af64f4d9076375eb1339fcb15cce5f6da6587c217d403c6e0119ad3c058f28`.
- Frame-15 visual evidence SHA-256 `ef0b5418d465bdfaddfcf3765e7fe1bd225120d4b2f1c86d300d8453f722f05e` (Sixtyfour, Inter, and JetBrains Mono rows all visibly rendered).
- Verbose output recorded five `Loading Astrid local fonts` completions and zero Google-font host markers. The full filtered receipt is `LOCAL_FONT_NETWORK_DENY.log`.

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
