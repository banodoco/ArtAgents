# Settled-plan wave 1 — synthesis (plan v2, snapshot 8323bcc7f350603a)

Critics: GLM 5.3 Flash ×3 (kiss-scope, reuse-order, validation-fit), independent, same immutable snapshot. Verdicts below are the oracle's dispositions.

## Accepted (feed to full-plan revision R2)

1. **Color parsing (W1A-1 refined by W1B-2).** W1A proposed deleting `_parse_color` for `PIL.ImageColor`; W1B empirically contradicted the blanket claim (`ImageColor.getcolor('rgba(0,0,0,0.75)', 'RGBA')` raises). **Disposition: accept W1B-2** — use `ImageColor` for hex/named forms; hand-parse only the `rgba(r,g,b,a)` form needed by text/shadow colors; share one branch.
2. **Canonical duration reuse (W1A-3 + W1B-1).** Implement `_text_window` as a thin wrapper over canonical `astrid/core/timeline/validators/timeline.py:128 _clip_duration_seconds` (re-exported `banodoco_schema.py:564`); support validates text timing through the same helper. Because canonical computes `to−from`, support must **reject text `from` explicitly** (consistent with media-bounds rejections). Accept both as one change.
3. **Stream-copy veto in two places, not three (W1A-2).** Keep support feature forcing and the command-builder guard; drop the run.py re-check (`run.py:121` merely relays the support feature — dead weight). Accept.
4. **Test distribution per batch (W1B-3).** Split task 6's tests into their batches (rasterize→1, support→2, argv→3, yaml retargets→4+5); task 6 keeps only live-smoke prep. Avoids red suite between batch commits. Accept.
5. **Support reject tests for x/y/width/height and text-on-audio-track (W1C-1).** Highest-risk silent-fallback surface (Remotion silently drops x/y). Accept.
6. **Dedupe argv `-t` assertion (W1C-2).** One assertion on input index + parsed value covers both listed forms. Accept.
7. **Smoke probe pinned to luma/alpha (W1C-3).** Drop the checksum alternative; luma/alpha also proves the output decodes. Accept.
8. **Precedent comment in font resolver (W1B-4).** One-line comment naming `visual_understanding`/`timeline_visualize` precedent to slow drift. Accept.

## Rejected

None.

## Investigate

None.

## Wave disposition

All 8 findings accepted → material revision required (R2 → plan v3). Per skill, a fresh settled-plan wave (wave 2) runs on the entire v3 before the plan is final.
