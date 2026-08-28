# Batch 6 checkpoint evidence

- Commit: `a5fc84f8` "megado B6: correct ffmpeg text extension doc to shipped behavior" (parent 5fd08a28)
- Delta: `docs/ffmpeg-text-extension.md` only (121 insertions, 72 deletions; doc now 129 lines). Criterion: no other docs touched.
- Executor: GLM 5.3 Flash (2400s budget exhausted after editing but before committing; host committed the executor's edit verbatim — recorded here).
- All T8 claim corrections present in the rewritten doc (filtergraph location; `_parse_fades` single reader; fail-closed system-TTF font with no load_default/fonttools/woff2/PowerGrotesk; ImageColor+rgba color and `_parse_text_shadow`; canonical `_clip_duration_seconds` wrap + text `from` reject; `-loop 1 -t END` overlay cap; ffmpeg-first auto-route with Remotion fail-closed fallback; legacy_hybrid unchanged/unused on default path; intro storyboard not the smoke target; two-place stream-copy veto; live smoke window observation). No forbidden claims.
- Claim-level verification (warning name, blur sigma, stream-copy gating details) delegated to oracle check-in against code.
- Acceptance criteria B6 (tasklist): 1-4 — verified by oracle check-in (checkins/batch-6.md).
