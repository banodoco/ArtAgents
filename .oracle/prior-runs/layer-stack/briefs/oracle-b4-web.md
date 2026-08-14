# Oracle Batch 4 — web: Remotion 4.0.509 VP9 alpha

Read-only research. Do not edit the repo. <250 words.

HOST-PROBED (do not contradict; explain):
- Remotion 4.0.509: `--codec=vp9 --pixel-format=yuva420p` is *accepted* (pixel-format.js allows yuva420p for vp8/vp9) but the emitted file is **yuv420p, no alpha**.
- Same version: `--codec=prores --prores-profile=4444 --pixel-format=yuva444p10le` emits **yuva444p12le** (alpha present).

Search the web:
1. "remotion vp9 alpha not working" / "remotion 4.0.5 yuva420p" / "remotion transparent webm vp9"
2. Remotion docs: transparent video / chrome transparency / ProRes 4444 vs VP9.
3. Any known bug in 4.0.5x, required extra flags (`--video-bitrate`, `--codec=vp8`, chrome `--enable-features`, `gl=angle`), or a later remotion version that fixed VP9 alpha.

## Report

```
KNOWN-BUG: yes|no|unclear — citation
FIX-IN-4.0.509: flag combo that yields yuva420p | none found
DOCS-PATH: what remotion currently documents as the alpha recipe (VP9? ProRes? PNG sequence?)
UPSTREAM-FIX: version if any
RECOMMEND: keep-vp9 | switch-prores | png-seq — one sentence
```

Cite URLs. Do not invent a flag combo the host did not probe.
