# Oracle Batch 3 — elegance + semantics critique (KISS / YAGNI)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan
Read: `astrid/packs/rendering/finalizers/compositor/run.py`,
`astrid/packs/rendering/finalizers/compositor/finalizer.yaml`,
`astrid/packs/rendering/finalizers/ffmpeg/run.py` (compare size/shape only),
`tests/packs/rendering/test_ffmpeg_compositor.py`,
`.oracle/plan.md` Batch 3, `.oracle/tasklist.md` Batch 3,
`.oracle/briefs/batch-3.md`, `.oracle/checkins/batch-1.md` (pad short layers incl. z=0).
Commit edf0859a. Read-only. Take a position. <350 words.

Bias: KISS, YAGNI, cut scope that isn't pulling its weight. Flag over-engineering, not just bugs. Do not propose planner/renderer work (later batches). Do not implement fixes.

## Judge these six calls. Yes/no + one evidence sentence each.

A. **`eof_action=pass` vs `repeat`.** Flash claims `repeat` freezes the last frame of a short layer and `pass` correctly reveals the accumulated result below. Is that true for ALL short-layer cases: top short, bottom (z=0) short, BOTH short, middle of N>2 short? Any case where `pass` leaves a transparent/black gap that `repeat` would wrongly fill? Does the `color=black` base + overlay-pass actually pad z=0 (oracle note)?

B. **`support()` honesty.** Does it reject layer=None, single-z, blend!=normal, <2 distinct z? Strict enough that concat stays the only layer=None consumer? Tasklist also says "mixed windows" — does support reject mixed/partial windows, or accept them and pad (per oracle note)? Is that a conflict or the right call?

C. **Frame-count authority.** Is output length guaranteed = `plan.total_frames` (never sum)? `-t total_seconds` + color duration: any off-by-one at 30000/1001 or non-integer fps? Audio apad/`-t` interaction?

D. **Pixel proofs.** Meaningful (real decoded pixels) or tautological (command-string only)? Holes that are Batch-3 defects vs LEAVE: no opacity<1 pixel proof, no short-bottom, no NTSC fps, no premultiplied (brief says leave premultiplied).

E. **Elegance.** `run.py` is ~1083 lines. Proportional to the existing ffmpeg finalizer? Dead code, duplicated helpers, over-abstracted graph builder, unused blend hooks? What would you cut?

F. **Freeze + concat isolation.** test_freeze only added the id? Concat tests untouched?

## Report shape

```
A: pass-correct | pass-wrong | mixed — ...
B: honest | leaky — ...
C: guaranteed | hole — ...
D: meaningful | tautological | holes-that-matter — ...
E: proportional | overbuilt — ...
F: isolated | contaminated — ...
MUST-FIX-NOW: none | 1-3 concrete Batch-3 defects (file:line + why it fails the checkpoint)
DEFER: Batch 4/5/6 or LEAVE
```
