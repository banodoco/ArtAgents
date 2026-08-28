# Rework tasklist — final review attempt 1 (supplemental; frozen tasklist unchanged)

Sources: final review pass 1 (GLM, findings/final-review-glm.txt: ISSUES) + pass 2 (Grok, /tmp/final-review-grok-out.md → checkins/final-review-grok.md: ISSUES, 1 blocker). Oracle triage below; all rework items are `normal` (GLM 5.3 Flash). Acceptance: fresh independent full-criteria review pass after execution.

## R1 — Fade correctness + fail-closed window checks + bold dedupe (`normal`, GLM)

| # | Finding | Oracle disposition | Required outcome |
|---|---|---|---|
| 1 | **BLOCKER (Grok): `fade=…:d=0.000000` is not a no-op.** ffmpeg `fade` with `duration=0` uses `nb_frames` (default 25) → ~25-frame ease. Plan's "always emit both fades" decision rested on E1 verifying exit code only. No-envelope text (brand wordmark) silently eases in. | **ACCEPT — plan decision corrected.** | `command.py` emits each fade filter **only when its duration > 0** (in and out independent). No-envelope → no fade filters → truly instant. Hang protections (`-t END`, spine-first, no `-shortest`) unchanged. Update `test_both_fades_emitted_even_at_zero_duration` to assert ABSENCE at d=0 and presence when >0 (both sides independent). |
| 2 | **(GLM) Text past media spine silently truncated.** Support accepts a text window ending after visual media coverage; spine duration is media concat, so the text tail is dropped invisibly. | **ACCEPT — fail-closed.** | Support rejects any text clip whose `_text_window` end exceeds the visual media coverage end (same spirit as `text_only_no_media` rejection). Test: text extending past last media end → supported=False with reason. |
| 3 | **(Grok) Fade envelope not validated against window.** `fade_in+fade_out > end-at` → `st` negative/overlapping → wrong alpha. | **ACCEPT — fail-closed, same class as R1-2.** | Support rejects text clips where `fade_in + fade_out > (end − at)`. Test included. |
| 4 | **(GLM) `_text_wants_bold` mirrors the rasterizer's bold rule.** | **ACCEPT — single surface (wave-1 spirit).** | Move the bold predicate to `text.py` (e.g. `text_wants_bold(clip)`); support and rasterizer both use it; delete the mirror. |
| 5 | **(Grok nit) `command.py:1` docstring still "media-only renderer"; `_support_load_failure` omits new feature keys.** | **ACCEPT (hygiene).** | Fix the docstring line; add `text_overlay: False, fade_envelope: False` (with `media_only: True`) to the support-load-failure feature dict. |

Validation: `pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q` green + `pytest tests/core/rendering/test_cli.py -q` green; commit `megado R1: fade d=0 emission fix + fail-closed text window checks`.

## Dispositions without rework (recorded)

- (Grok) `text.fontFamily`/`italic` silent-ignore → **REJECT the fail-closed change**: settled parity decision (plan v2/v3, three settled waves, pre-exec review) — the chosen parity bar is the Three.js fixed stack, which itself ignores `fontFamily`; failing closed would push the cut pipeline's timelines back to Remotion, defeating the run. Disclosed in shipped doc ("text.fontFamily and italic are ignored (fixed stack)").
- (Grok) Track-layering divergence (text always above media) → **REJECT**: documented slide-overlay parity bar; no evidence of real timelines needing text-below-media.
- (Grok) Text `to`-vs-hold window semantics divergence vs Remotion text-card hold-only → **REJECT**: canonical `_clip_duration_seconds` reuse was accepted in settled wave 1; golden examples use `hold`.
- (GLM) Resolver precedent comment "stale/garbled" → **REJECT**: comment is verbatim the frozen tasklist's mandated wording (B1 AC 2, PASS by Grok); it names the precedent split deliberately.
- (GLM) z-order parity test vs Remotion reference → **REJECT**: unverifiable out-of-repo reference; no evidence of impact.
- (Grok) Private-helper imports across backend modules → **REJECT**: same-package reuse, no public API needed (a public export was explicitly ruled out by the plan).
