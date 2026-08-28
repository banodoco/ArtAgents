# Settled-plan wave 2 — synthesis (plan v3, snapshot 0a27e8b563a0dcf9)

Critics: GLM 5.3 Flash ×2 (simplicity-reuse-order, validation-goal-coverage), independent, same immutable v3 snapshot. Wave-1 dispositions embedded; no repeats raised.

## Accepted (feed to full-plan revision R3)

1. **Single fades normalizer (W2A-1).** `clip.effects` accepts map or list-of-objects, but v3 specifies validate-in-support + extract-in-run — a drift risk (list accepted, map-only extracted → silent no-fade). Fix: `_parse_fades(effects) -> (fade_in, fade_out)` in `text.py` (task 1), consumed by both support (task 2) and run.py (task 4).
2. **Single shadow-parse surface (W2A-2).** Support must call `_parse_text_shadow` (which returns the color) rather than hand-splitting the CSS string to reach a color for `_parse_color`.
3. **Validation command gap (W2B-1).** `tests/core/rendering/test_cli.py:82` (clip_types prefix assertion) is outside `pytest tests/packs/rendering/`. Add `python -m pytest tests/core/rendering/test_cli.py -q` to the plan's validation list.
4. **Assert declared observable contracts (W2B-2).** Add: one accept-test line asserting support report features (`media_only: False`, `text_overlay: True`, `stream_copy: False` when text present); one dict-equality assertion on the yaml `features` block in the yaml test.
5. **Smoke timed-window assertion (W2B-3).** Live smoke adds: post-END sampled frame luma ≈ pre-AT frame (overlay window is observed live, not only argv-asserted). One extra frame extract, no new fixture.

## Rejected

None.

## Investigate

None.

## Noted, no action

- W2A-3: batch order verified safe as written (service.py:1046-1054 statically rejects clipTypes outside manifest clip_types before support runs, so yaml-last keeps batches 2-4 behaviorally inert); folding checkpoints 2-5 is neutral. Keep 1→2→3→4+5→6→7→8.

## Wave disposition

5 accepted → material revision R3 (v4), then a fresh settled wave (wave 3) on the entire v4. Plan settles only when v4 is STABLE and wave 3 yields no accepted material simplification.
