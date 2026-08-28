# Executor brief — Batch 6 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 6. Mechanical execution only: correct EXACTLY the claims listed — edit ONLY `docs/ffmpeg-text-extension.md`, no other file. If you believe a claim in the spec is wrong, STOP and report.

## North Star (complete — advance this end state; avoid its anti-patterns)

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


## Your task

## Batch 6 — Docs (claims match shipped behavior)

**Depends on:** B5 PASS.  
**Advances agent-goal:** done-criterion 6 (docs touched only where behavior/claims changed).  
**North Star:** no routing lies in documentation — do not claim the hybrid planner still intercepts text; do not claim yaml/support are “not enough” to change default routing (v1 was wrong). Avoid scope creep: this file only; no planner/Remotion docs.

### T8 — `docs/ffmpeg-text-extension.md` only

**Files:** `docs/ffmpeg-text-extension.md`

**Changes — correct claims to match shipped behavior:**
- Filtergraph lives in `command.py`, not a section loop in `run.py`.
- Fades are `clip.effects` via one `_parse_fades` shared by support and run.
- Font is system Arial/DejaVu TTF, fail-closed (no `load_default()`, no fonttools, no woff2, no PowerGrotesk).
- Color is ImageColor + `rgba()`; shadow is `_parse_text_shadow` (support does not re-split CSS).
- Text window wraps canonical `_clip_duration_seconds`; text `from` is rejected.
- Overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END` (not `-shortest`, not `-t END-AT`).
- Default `rendering.render` is ffmpeg-first auto-route, so media+text that pass support now render on ffmpeg. Remotion remains the fallback when ffmpeg fail-closes (text-card, media hold, extra visual media, missing font, text `from`, x/y transforms, etc.).
- `legacy_hybrid` is unused on the default path and is unchanged.
- Intro storyboard is not the smoke target.
- Stream-copy is vetoed by support features and the command builder, not a third `run.py` branch.
- Live smoke observes the overlay window (mid-window visible, post-END matches pre-AT).

Do **not** claim the hybrid planner still intercepts text. Do **not** claim yaml/support are “not enough” to change default routing. Do not edit planner/Remotion docs.

**Classification:** `normal` — claim-correction in one seed-plan file against a pinned list. Proposed model: GLM 5.3 Flash.

### Checkpoint B6

**Acceptance criteria (oracle verifies):**
1. Only `docs/ffmpeg-text-extension.md` is edited for docs.
2. Every claim bullet of T8 is present and matches the shipped code: filtergraph location (`command.py`); fades are `clip.effects` via one `_parse_fades` shared by support and run; font is system Arial/DejaVu TTF fail-closed (no `load_default()`, no fonttools, no woff2, no PowerGrotesk); color is ImageColor + `rgba()` branch, shadow via `_parse_text_shadow`; text window wraps canonical `_clip_duration_seconds` and text `from` is rejected; overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END`; default `rendering.render` is ffmpeg-first auto-route with Remotion as fail-closed fallback; `legacy_hybrid` unused on the default path and unchanged; intro storyboard not the smoke target; stream-copy vetoed by support features + command builder (no third `run.py` branch); live smoke observes the overlay window (mid-window visible, post-END ≈ pre-AT).
3. No claim that the hybrid planner intercepts text, and no claim that yaml/support are "not enough" to change default routing.
4. No other docs files touched (`git diff --name-only c6c505af..HEAD -- docs/` shows only `ffmpeg-text-extension.md`).

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/ -x -q
python -m pytest tests/core/rendering/test_cli.py -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS.

---



## Execution instructions
1. You are in the worktree on branch `megado/oracle-run-ffmpeg-text` (HEAD 5fd08a28 = B5). All code is landed and gated. Read the current `docs/ffmpeg-text-extension.md` and the shipped code it describes (`astrid/packs/rendering/backends/ffmpeg/{renderer.yaml,support.py,command.py,run.py,text.py}`) so every corrected claim matches shipped reality.
2. Rewrite the doc so every bullet in the task's Changes list is true, and the "Implementation order"/claims reflect what shipped (text.py helper; support carve-outs; command.py overlay chain with `-t END` cap; run wiring; yaml declaration; live smoke instead of intro-storyboard testing).
3. Preserve the doc's purpose (it documents the extension) — keep it concise; do not pad it with process narrative, do not mention megado/batches/oracle.
4. Structure suggestion: Problem (unchanged intent), What shipped (backend-local text overlay support; capability declaration; default ffmpeg-first auto-route consequence), How it works (font resolver, color/shadow/fade parsing, text window, filtergraph shape with the exact overlay chain, stream-copy veto), Testing (unit + argv + live smoke description), Explicitly out of scope.
5. Validate: no test runs needed, but run `git diff --name-only` and confirm ONLY `docs/ffmpeg-text-extension.md` is modified.
6. COMMIT IMMEDIATELY: `git add docs/ffmpeg-text-extension.md`, message: `megado B6: correct ffmpeg text extension doc to shipped behavior`. Do not push.
7. Report: claim-by-claim confirmation, commit SHA, deviations (none allowed).
