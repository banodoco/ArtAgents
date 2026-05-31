# M4 — Remaining gap scenarios (discovery/authoring/refuse) + cross-scenario synthesis

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§3 matrix gaps, §4 build-first) and `tests/agentic/ADAPTER.md` (M1). Read both.

## Outcome
The remaining matrix-gap scenarios built on the Sisypy harness, plus the cross-scenario synthesis wiring restored, completing the extensive-coverage goal. After this milestone the suite covers every non-empty Domain×Challenge cell that doesn't require live GPU/cloud.

## Scope (IN)
Build these net-new scenarios (YAML + brief + rubric):
1. **`cross_pack_authoring`** [Authoring×Compose] — agent authors a NEW orchestrator that composes executors from two DIFFERENT packs (e.g. `editorial.transcribe` → `foley.foley_review`); assert it discovers both via search, authors via the DSL, and `author check`/compile passes.
2. **`broken_authoring_fix`** [Authoring×Repair, adversarial] — an existing orchestrator has a compile-breaking DSL bug; agent runs `author check`, reads the error, fixes the DSL, recompiles clean. Proves the compile-error surface is actionable.
3. **`no_tool_exists_pushback`** [Discovery×Refuse] — brief asks for a capability with NO matching tool; agent must search with ≥2-3 distinct query formulations, conclude nothing matches, and push back cleanly instead of hallucinating a tool id or authoring something broken.
4. **`discover_projects_runs_sessions`** [Discovery×Infrastructure] — agent must discover existing projects/runs/sessions (not just packs) via `projects ls` / `runs ls` / `sessions ls` before acting. Fills the Discovery×Infra gap.
5. **`author_run_revise_loop`** [Authoring×Execute, scale M/L] — full iterative loop: author an orchestrator, run it, observe a wrong output, revise the DSL. Proves the end-to-end development cycle.
6. **`recover_from_no_search_results`** [Discovery×Recover] — first search returns zero hits (terms chosen to miss); agent must rephrase/broaden/`list`-fallback rather than concluding "no tool exists" after one query.
7. (Optional, if budget allows) **`ambiguous_brief_clarification`** [Execution×Refuse] — underspecified brief (no media path/project); agent asks a clarifying question rather than guessing.

Plus:
- **Cross-scenario synthesis wiring** — restore the `pattern_finder`-equivalent capability on the Sisypy stack: a read-only post-run synthesis that reads every scenario's `summary`/evidence aggregate and surfaces recurring friction patterns across agents/models. Wire it to Sisypy's cross-run synthesis if supported, else a thin Astrid-side script invoked post-sweep.
- **Coverage matrix doc** — `tests/agentic/COVERAGE.md` rendering the Domain×Challenge matrix with every scenario placed in its cell, so future gaps are visible at a glance.

## Locked decisions
- Universal checks (M1) apply automatically; these scenarios add scenario-specific rubric items only.
- Discoverability scenarios assert the RIGHT discovery path from evidence (e.g. a `search`/`list` call BEFORE any authoring/execution; ≥2 query formulations before a no-results pushback) — per design §3 / discoverability dimensions.
- Refuse/pushback scenarios use the universal `claim-vs-evidence` + a scenario-specific "did not fabricate" enforced check.

## Open questions for the planner
- For `no_tool_exists_pushback` / `recover_from_no_search_results`: pick brief wording and missing-capability framing that reliably has no registry match but is plausible.
- Whether Sisypy provides native cross-run synthesis or whether to port the existing `pattern_finder.py` logic onto the new evidence-pack format.
- For `author_run_revise_loop`: a small orchestrator that can run structurally and produce an observably-wrong-then-fixed output.

## Constraints
- Structural mode: no network/GPU/spend.
- Synthesis is read-only over frozen reports; it never mutates evidence or gates a scenario.

## Done criteria
- All new scenarios load and structurally pass.
- The synthesis step runs over a multi-scenario structural sweep and emits a synthesis report.
- `tests/agentic/COVERAGE.md` exists and places every scenario (migrated + M3 + M4) in the matrix; empty cells are explicitly labeled (e.g. "requires live GPU — out of scope").
- The full suite runs via the parallel/structural path end-to-end.

## Touchpoints
- `tests/agentic/scenarios/` (new YAML), `tests/agentic/briefs/` (new briefs), synthesis script, `tests/agentic/COVERAGE.md`, read-only `astrid/core/orchestrator/*` (author/compile), `astrid/packs/*`, the M1 adapter.

## Anti-scope
- Do NOT touch `astrid/` production code or fix filed discoverability tickets — scenarios probe/expose, they don't fix metadata.
- Do NOT change M1's adapter contract non-additively.
- Do NOT build live-GPU/Reigh/RunPod or Supabase-sync scenarios — those are explicitly out of scope (note them as future work in COVERAGE.md).
