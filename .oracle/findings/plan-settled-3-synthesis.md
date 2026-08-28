# Settled-plan wave 3 — synthesis (plan v4, snapshot 91e2ca981c7539d2)

Critics: GLM 5.3 Flash ×2 (simplicity-reuse-order, validation-goal-coverage), independent, same immutable v4 snapshot. Wave-1/2 dispositions embedded; no repeats raised.

## Dispositions

- **W3A (simplicity-reuse-order): NO MATERIAL FINDINGS.** Verification sweep confirms: complete red-suite set is exactly the two in-commit retargets the plan pins; plan-vs-reality claims verified (command.py:182-205, support.py gates, hype track kinds); nothing deletable/mergeable; batch order simplest-safe.

- **W3B-1 (fade_envelope feature assertion): ACCEPT** — extend accept test with `fade_envelope is True` + one no-effects text accept asserting `False`.
- **W3B-2 (ink-position rasterize test): ACCEPT** — one rasterize test asserting ink bbox lands in the anchored region (top-right + offsets), skip-if-no-font guard as siblings.
- **W3B-3 (task-4 spec-builder unit test): ACCEPT** — one test on the private spec-builder (patched rasterize; assert at/end via `_text_window`, fades via `_parse_fades`).
- **W3B-4 (pin mid-window smoke sample): ACCEPT** — smoke samples mid-window (e.g. t=1.5 for window [1,2]), not at window start.
- **W3B-5 (drop duplicate text-card reject from new list): ACCEPT** — already pinned by retained `test_support_rejects_non_media_timeline`.

## Materiality determination (oracle)

W3B items are test-detail micro-additions/one dedupe inside existing tasks — they do not change task structure, dependencies, batch order, scope, or any architectural decision. Disposition: **below materiality for a fourth full-plan revision cycle**. They are accepted and enter the frozen tasklist as explicit acceptance-criteria items (Phase 4), where the pre-execution contract review independently verifies plan↔tasklist agreement. This honors the findings without an indefinite micro-revision loop.

## Wave disposition

Plan v4 = settled. W3A explicit NO MATERIAL FINDINGS; W3B accepted items carried into tasklist freeze. Skill's settled condition satisfied (STABLE confirmed on v3 lineage; latest wave yields no accepted material SIMPLIFICATION — W3B-5 is minor and lands in the tasklist; no unresolved investigations).
