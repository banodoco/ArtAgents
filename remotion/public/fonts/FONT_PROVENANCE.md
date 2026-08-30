# Astrid local font provenance

These are the only font binaries used by the Remotion render. They are bundled
so an offline render never asks Google Fonts, a CDN, or another network host
for CSS or font bytes. `OFL-1.1.txt` is shipped beside these binaries and
contains the complete license text and copyright notices.

The upstream Google Fonts repository revision used for the family and license
records below is:

`ade3d1533e06b2b1462ffcde8e08b129627ca360`

All three families are distributed under the SIL Open Font License, Version
1.1. The local binary SHA-256 values below are the acceptance-manifest values;
the upstream Git blob values identify the authoritative source record and are
not expected to equal a locally subsetted or format-converted binary.

## Sixtyfour

- Theme role: 2RP heading (`Sixtyfour`, variable BLED/SCAN axes).
- Local file: `Sixtyfour.woff2` (7,608 bytes).
- Local SHA-256: `0c35bb8333a12a822333f10fc4fd22e607b80a254b8b31faa8eed1cd4badc24e`.
- Upstream source: [homecomputer-fonts Sixtyfour webfont](https://github.com/jenskutilek/homecomputer-fonts/blob/22842dfb97fd3e7970383625cd3d10108edb8b5e/Sixtyfour/fonts/webfonts/Sixtyfour%5BBLED%2CSCAN%5D.woff2).
- Upstream revision: `22842dfb97fd3e7970383625cd3d10108edb8b5e`.
- Upstream Git blob: `368300391c703dcc22e6ea33fa9cff1cd377d385`.
- License: SIL Open Font License 1.1; copyright notice is `Copyright 2021 The Sixtyfour Project Authors (https://github.com/jenskutilek/homecomputer-fonts)`.
- Google Fonts curation record: `ofl/sixtyfour/` at the pinned Google Fonts revision above; its source TTF blob is `32985b4486ba627ad9b044be33b6d801b2d6d171`.

## Inter

- Theme role: 2RP body text.
- Local files: `Inter-Regular.woff2` (27,380 bytes), `Inter-Bold.woff2` (19,980 bytes).
- Local SHA-256: `39689184132e9fba8fb1066f429125d14445352a566f47f4edcae7c3c90e486d` (regular); `47d42151dff6d13f1c2b9a1f278290f625593c1f01c89612ee4ae7f063167f7a` (bold).
- Upstream family: [rsms/inter](https://github.com/rsms/inter); curated license/source record is [Google Fonts `ofl/inter`](https://github.com/google/fonts/tree/ade3d1533e06b2b1462ffcde8e08b129627ca360/ofl/inter).
- Upstream revision: `ade3d1533e06b2b1462ffcde8e08b129627ca360`.
- Upstream Git source blob: `047c92f6e2212473dc436020afed689527076d44` (`Inter[opsz,wght].ttf`).
- License: SIL Open Font License 1.1; copyright notice is `Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter)`.

## JetBrains Mono

- Theme role: 2RP monospace text.
- Local files: `JetBrainsMono-Regular.woff2` (2,180 bytes), `JetBrainsMono-Bold.woff2` (13,352 bytes).
- Local SHA-256: `1b53536573e8f2e886848fee9a53c278a8f92b02ac794a83437ad9277120df47` (regular); `8df3ca627bd8e1cb0e5414f7429fe7a2cf82732b0fc43f2d05bc2c471b64fcfc` (bold).
- Upstream family: [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono); curated license/source record is [Google Fonts `ofl/jetbrainsmono`](https://github.com/google/fonts/tree/ade3d1533e06b2b1462ffcde8e08b129627ca360/ofl/jetbrainsmono).
- Upstream revision: `ade3d1533e06b2b1462ffcde8e08b129627ca360`.
- Upstream Git source blob: `aa310be8b717fe3774f9444dd89d5f4101cc6d10` (`JetBrainsMono[wght].ttf`).
- License: SIL Open Font License 1.1; copyright notice is `Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)`.

## Acceptance contract

`src/fonts.ts` must remain the sole source of the local `@font-face` rules.
Every family named by the 2RP theme must have a local face in that list. The
loader waits for `document.fonts.load` and verifies `document.fonts.check` for
each family/weight; any missing face cancels the Remotion render. The focused
test also rejects hosted font imports, URL fetches, and missing glyph-proof
coverage.
