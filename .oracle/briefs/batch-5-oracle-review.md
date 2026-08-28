# Independent review pass — Batch 5 checkpoint (oracle-commissioned)

You are an independent reviewer for megado Batch 5 (live media+text smoke). Read the code. Do not edit files. Do **not** re-run the live pytest node (host/oracle already ran T7 once: `python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q` → 1 passed in 11.12s; raw output `.oracle/evidence/batch-5-live-smoke.txt`). You MAY grep, read, and run tiny Python one-liners that inspect source (no live ffmpeg). Return a structured verdict with file:line evidence.

Bias toward elegance (KISS, YAGNI): flag overengineering, not just bugs. Cut scope that isn't pulling its weight. Verdict is binary: first line exactly `PASS` or `ISSUES`.

## North Star (complete — disposition every principle and anti-pattern)

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

## Scope of this batch

T6 authors ONE live smoke in `tests/packs/rendering/test_ffmpeg_text.py` only. T7 is the host/oracle live invocation (already done; do not re-run). No more unit/support/argv/yaml tests. No production-code edits. No new fixtures. No checksums. Not the intro storyboard.

Commit under review: `5fd08a28` (parent `4ea29d62`).
Diff: `git diff 4ea29d62..5fd08a28`
Files that should be in the delta: `tests/packs/rendering/test_ffmpeg_text.py` only.

## What to read

1. `git diff 4ea29d62..5fd08a28` — confirm one file, one new test, no checksum/hashlib, no new fixture files, no storyboard.
2. `tests/packs/rendering/test_ffmpeg_text.py` — `test_live_media_plus_text_smoke` and its helpers (`_extract_frame`, `_luma_stats`, `_skip_if_no_font`).
3. `.oracle/evidence/batch-5-live-smoke.txt` — T7 host evidence (do not re-run).
4. Confirm production files (`run.py`, `support.py`, `command.py`, `text.py`, `renderer.yaml`) are **not** in the diff.
5. Confirm no new files under `tests/fixtures/` or elsewhere.

## Task contract (T6)

- Minimal timeline: one `from`/`to` visual media clip (tiny generated **constant-color** H264 via lavfi→libx264, the suite's compositor/finalizer pattern), one `clipType: "text"` with `hold`, `params.anchor`, `effects.fade_in`/`fade_out`, optional audio.
- Window strictly inside the media (e.g. media 4s, text `at=1` `hold=1`, fades `0.2/0.2` → overlay `[1, 2]`).
- Invoke `rendering.ffmpeg` support+render **directly** (`run.main` or `ffmpeg.render` / pack `run` helpers).
- Assert: `supported is True`; output exists; ffprobe has video and a **finite duration** (hang regression: unterminated `-loop 1`).
- **W3B-4:** sample a **mid-window** frame (e.g. `t=1.5` for window `[1, 2]`), **not** at window start / AT. That frame is not a blank plate via **luma and/or alpha only**.
- **One extra frame extract after END:** its luma ≈ the pre-AT plate (overlay gone). Same color plate, one more `-ss` extract. Encoder noise allowed; not pixel-identical; not a checksum. No overlay-PNG checksum.
- Skip if ffmpeg/ffprobe missing or font resolver returns `None` — skip, not fail.
- **Not** the 76-clip intro storyboard.
- `pytest-timeout` 120s is a suite backstop (`pyproject.toml`), not the hang fix. No per-test timeout decorator required as "the fix". Termination must come from input `-t` (already in B3); this smoke observes finite duration.

## Acceptance criteria — judge each one PASS or FAIL with evidence

1. `test_live_media_plus_text_smoke` exists with the timeline shape above (visual `from`/`to` media + text with hold/anchor/fades; optional audio allowed). Cite clip fields and sample times.
2. **W3B-4:** the in-window sample is mid-window (e.g. 1.5 for `[1, 2]`), not AT / window start. Cite the extract timestamp.
3. Post-END frame luma ≈ pre-AT plate; in-window frame is not a blank plate (luma and/or alpha). Cite assertions and the three extract times.
4. Output exists, plays, ffprobe duration is finite (no `moov atom not found`, no hang). Cite asserts. Treat T7 `1 passed in 11.12s` as live hang evidence — do not re-run.
5. Skip guards: missing ffmpeg/ffprobe or missing font → skip, not fail. Cite the two skip paths.
6. No checksum, no new fixture, no intro-storyboard target. Confirm via diff + grep (no hashlib/sha256/md5 of overlay PNG; media generated in `tmp_path`; no storyboard path).
7. Host/oracle evidence of the authoritative T7 command exists (`.oracle/evidence/batch-5-live-smoke.txt` shows 1 passed). Executor local green check during T6 is allowed; do not treat it as a duplicate-run FAIL.

## Load-bearing hunts (do not skip)

For each, cite the exact code path:

- Overlay window is strictly inside media: media `[0, 4]`, text `at=1` `hold=1` → `[1, 2]`.
- Mid-window extract is 1.5 (or equivalent interior), not 1.0 / AT.
- Post-END extract is after 2.0 (e.g. 2.6).
- Pre-AT plate extract is before 1.0 (e.g. 0.5).
- Finite-duration assert uses ffprobe (`duration_seconds` finite and bounded), not only `output.exists()`.
- `supported is True` is asserted before/around render.
- Invocation is pack-direct (`ffmpeg_run.support` / `ffmpeg_run.render` or `run.main`), not a Remotion path, not the intro storyboard.
- Skip uses `pytest.skip`, not `pytest.fail` / bare raise, for missing ffmpeg/ffprobe and missing font.
- No `@pytest.mark.timeout` presented as the hang fix; suite 120s backstop is fine.
- Delta is the test file only.

## Elegance critique (required)

Flag overengineering, extra fixtures, checksums, pixel-identity, intro-storyboard targeting, extra tests, production-code edits, a new helper package, or anything outside T6/T7. Optional audio and measuring the pre-AT plate from a live extract (vs computing it) are **in-spec** — do not FAIL those. Do NOT fail the batch for nits that still meet the contract. ISSUES only for contract holes or North Star anti-patterns that actually landed.

## Output shape (strict)

First line: `PASS` or `ISSUES`

Then:
- AC 1–7: each PASS or FAIL with file:line evidence (one line each).
- Load-bearing hunts: PASS/FAIL one-liners.
- North Star: one explicit ALIGNED / DRIFT / N/A disposition per principle and per anti-pattern. For this test-only batch, capability/yaml principles are N/A unless the smoke itself lies.
- Elegance: at most 5 nits; say "none" if none.
- If ISSUES: numbered list of required fixes. If PASS: "Issues: none."

Cap: 400 words after the first line. Evidence over narrative.
