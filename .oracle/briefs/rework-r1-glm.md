# Rework executor brief — R1 (megado run ffmpeg-text, final rework)

You are the NORMAL EXECUTOR for rework R1. Mechanical execution only. Every change below is oracle-triaged and pinned — implement exactly; if the spec seems wrong, STOP and report.

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


## Rework items (all ACCEPTED by oracle; implement every one)

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


## Execution instructions
1. Worktree branch `megado/oracle-run-ffmpeg-text`, HEAD a5fc84f8 (B6). Files: `astrid/packs/rendering/backends/ffmpeg/command.py`, `support.py`, `text.py`, and `tests/packs/rendering/test_ffmpeg_text.py` (+ possibly `test_ffmpeg_support.py`).
2. Item R1-1 (BLOCKER): in `command.py`'s overlay chain, emit `fade=t=in:…` ONLY when `fade_in > 0`, and `fade=t=out:…` ONLY when `fade_out > 0` (each side independent). No-envelope spec → NO fade filters at all. Do NOT touch the `-t END` cap, spine-first wiring, `enable='between(t,AT,END)'`, or the no-`-shortest` invariant. Update the existing zero-duration test to assert ABSENCE at d=0 (per side) and presence when >0; add/adjust the existing always-emit assertions accordingly.
3. Item R1-2: in `support.py`, reject any text clip whose `_text_window` end exceeds the end of the visual media coverage (max media clip end on the visual spine). Add test: text ending after last media end → supported=False with reason.
4. Item R1-3: in `support.py`, reject text clips where `fade_in + fade_out > (end − at)` (use `_text_window` + `_parse_fades`). Add test.
5. Item R1-4: move the bold predicate into `text.py` as a module-level function (e.g. `text_wants_bold(clip)` = `bool(text.bold) or params.weight >= 600`); `text.py` rasterizer and `support.py` both call it; delete `_text_wants_bold`.
6. Item R1-5: fix `command.py`'s module docstring first line (no longer "media-only"); in `run.py`'s `_support_load_failure`, include `text_overlay: False` and `fade_envelope: False` alongside `media_only: True`.
7. Validate ALL green: `python -m pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q` AND `python -m pytest tests/core/rendering/test_cli.py -q`.
8. COMMIT IMMEDIATELY once green: `git add` the touched backend files + test files, message: `megado R1: fade d=0 emission fix + fail-closed text window checks`. Do not push.
9. Report: per-item confirmation, pytest summaries, commit SHA, deviations (none allowed).
