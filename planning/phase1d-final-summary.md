# Phase 1d — Codex final revision (STABLE)

R1–R25 final tasklist, compositor-parity findings absorbed, verdict **STABLE — ready for conversion to batched execution plan**. No A12+ warranted.

Full text captured from codex phase-1d run (`/tmp/codex_phase1d_out.txt` lines 3931–4060); canonical copy in this directory as `phase1d-final-tasklist.md` (written next).

Key A11 deltas absorbed:
- R1 freezes three desert facts: authored visual-only 13.8667s, frame-quantized visual 332fr/13.8333s, all-track composition 2352fr/98s (audio [12,2352) always determines total).
- R2 = closed compositor-parity contract: canonical `duration.py` mirroring `@banodoco/timeline-composition` v0.0.6 (hold overrides from/to, /speed, Math.round, 1-frame minimum, no track/muted filter, transition 12-frame fallback, visual tracks reversed → first config track topmost); F1–F8 parity fixtures + independent ~20-line Python oracle; read-only snapshot of pinned compositor source.
- R7 models authored / frame-quantized / transition-effective intervals separately; config order + bottom-to-top paint order.
- R10 uses compositor frames for geometry; topmost-first lanes, reversed bottom-to-top visual painting.
- R17 absorbs F1–F8 + parity drift; R18/R20/R22 distinguish authored vs rendered time.

Plan corrections consolidated: 19 corrections (pure replay authority; SNS envelope; named duration metrics; compositor v0.0.6 as rendered truth; hold-overrides-then-speed; Math.round + 1-frame min; all-clip composition duration; transition precedence; z-order reversal; clean core/timeline helpers, storyboard frozen; asset sourceId/sourceVersion/expected-observed hashes; contained sources/ paths; requires_timeline:false + sorted timeline_ids + run-owned retention; narrow sessionless --from-view; UUID+ULID; full validation after replay; no rasterized-SVG acceptance; extend existing Sisypy adapter; ordered image blocks + pinned model; defer arbitrary executor input; upstream baseline ordering).
