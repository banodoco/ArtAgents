# Executor brief — Batch 5 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 5. Mechanical execution only: author EXACTLY the test specified — no extra tests, no new fixtures, no scope widening. If you believe something in the spec is wrong, STOP and report.

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

## Batch 5 — Live smoke (author + host-run)

**Depends on:** B4 PASS (implementation + co-located unit/support/argv/yaml tests already green).  
**Advances agent-goal:** done-criterion 1 (media+text renders: visible, positioned, timed, faded, plays) and done-criterion 5 (short live render smoke, real ffmpeg).  
**North Star:** hang is caught by a real ffmpeg, not only argv; output parity is “text visible,” not pixel-match; overlay **timing** is observed live. Avoid checksum smoke, extra fixtures, and treating liveness as pixel-identity.

T6 is executor-authored. T7 is the **authoritative host/oracle invocation** of that same test (one owner runs live validation once). Executors may do one local green check while authoring; they must not duplicate extra paid/live runs.

### T6 — Author `test_live_media_plus_text_smoke`

**Files:** `tests/packs/rendering/test_ffmpeg_text.py` only (add the live test). No more unit/support/argv/yaml tests here.

**Changes:**
- Minimal timeline: one `from`/`to` visual media clip (tiny generated **constant-color** H264 via the suite’s real-ffmpeg fixture pattern from `test_ffmpeg_finalizer.py` / compositor smokes), one `clipType: "text"` with `hold`, `params.anchor`, `effects.fade_in/fade_out`, optional audio.
- Window strictly inside the media (e.g. media 4s, text `at=1` `hold=1`, fades `0.2/0.2` → overlay `[1, 2]`).
- Invoke `rendering.ffmpeg` support+render **directly** (protocol `run.main` or `ffmpeg.render`).
- Assert: `supported is True`; output exists; ffprobe has video and a **finite duration** (hang regression: unterminated `-loop 1` yields timeout / `moov atom not found`).
- **W3B-4:** sample a **mid-window** frame (e.g. `t=1.5` for window `[1, 2]`), **not** at window start. That frame is not a blank plate via **luma and/or alpha only**.
- **One extra frame extract after END:** its luma ≈ the pre-AT plate (overlay gone). Same color plate, one more `-ss` extract. No new fixture. Encoder noise allowed; not pixel-identical; not a checksum. No overlay-PNG checksum.
- Skip if ffmpeg/ffprobe missing or font resolver returns `None`.
- **Not** the 76-clip intro storyboard (extra visual media and other pre-existing ffmpeg refusals).
- `pytest-timeout` 120s is a backstop, not the fix. Termination must come from input `-t`.

**Classification:** `normal` — one smoke test copying an existing lavfi→libx264 pattern with pinned sample times. Proposed model: GLM 5.3 Flash.

### T7 — Host-run live smoke (done-criterion 5)

**Files:** none. No code.

**Command (authoritative, host/oracle runs once):**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q
```

Same assertions as T6, including mid-window ink and post-END luma ≈ pre-AT.

**Classification:** `normal` — run an already-authored pytest node; not a judgment kernel. Proposed model: n/a (host/oracle owns the live invocation per the agent-goal validation contract). Executor local green check during T6 is allowed; do not duplicate the host run.

### Checkpoint B5

**Acceptance criteria (oracle verifies):**
1. `test_live_media_plus_text_smoke` exists with the timeline shape above.
2. **W3B-4:** the in-window sample is mid-window (e.g. 1.5 for `[1, 2]`), not AT / window start.
3. Post-END frame luma ≈ pre-AT plate; in-window frame is not a blank plate (luma and/or alpha).
4. Output exists, plays, ffprobe duration is finite (no `moov atom not found`, no hang).
5. Skip guards: missing ffmpeg/ffprobe or missing font → skip, not fail.
6. No checksum, no new fixture, no intro-storyboard target.
7. Host/oracle evidence of the authoritative command above (one run). Executor may have one local green check in the implementing batch.

**Validation commands:**
```bash
# executor local green check while authoring (at most once)
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q

# authoritative host/oracle run (once; this is T7)
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS (the test file). Host-run evidence goes under `.oracle/evidence/`.

---



## Execution instructions
1. You are in the worktree on branch `megado/oracle-run-ffmpeg-text` (HEAD 4ea29d62 = B4). Everything is implemented: `text.py` (B1), support (B2), overlay filtergraph (B3), run wiring + yaml (B4).
2. Read first: `tests/packs/rendering/test_ffmpeg_finalizer.py` and the compositor smokes for the real-ffmpeg fixture pattern (lavfi color source → libx264), and `tests/packs/rendering/test_ffmpeg_text.py` for existing conventions/helpers.
3. Author `test_live_media_plus_text_smoke` in `tests/packs/rendering/test_ffmpeg_text.py` EXACTLY per the task spec:
   - Minimal timeline: one `from`/`to` visual media clip (tiny CONSTANT-COLOR H264 generated via the suite's real-ffmpeg fixture pattern), one `clipType: "text"` clip with `hold`, `params.anchor`, `effects.fade_in`/`fade_out`, optional audio.
   - Window strictly inside the media (e.g. media 4s; text `at=1`, `hold=1` → overlay window [1, 2]; fades 0.2/0.2).
   - Invoke `rendering.ffmpeg` support+render DIRECTLY (protocol `run.main` or the pack's render entry — read `run.py` to pick the same invocation style sibling tests use).
   - Assert: `supported is True`; output exists; ffprobe has video and FINITE duration (hang regression guard: unterminated `-loop 1` yields timeout / `moov atom not found`).
   - W3B-4: sample a MID-WINDOW frame (t=1.5 for window [1,2]) — NOT at window start — and assert it is not a blank plate via luma and/or alpha.
   - One extra frame extract AFTER END (e.g. t=2.6): its luma ≈ the pre-AT plate (overlay gone). Encoder noise allowed; not pixel-identical; NO checksum of the overlay PNG.
   - Skip guards: missing ffmpeg/ffprobe OR font resolver returns None → `pytest.skip`, not fail.
   - NOT the intro storyboard. No new fixture files beyond what the test generates in tmp_path.
4. Local green check (at most ONCE): `python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q` — must pass (or skip only for the documented guard reasons).
5. Also confirm the rest of the file stays green: `python -m pytest tests/packs/rendering/test_ffmpeg_text.py -q`.
6. COMMIT IMMEDIATELY once green: `git add tests/packs/rendering/test_ffmpeg_text.py`, message: `megado B5: live media+text smoke (hang, window, parity guards)`. Do not push.
7. Report: test code summary, pytest output, commit SHA, deviations (none allowed).
