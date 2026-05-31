# M5 — Remaining gap scenarios (discovery/authoring/refuse) + synthesis + decommission legacy

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§3 matrix gaps, §4) + `tests/agentic/ADAPTER.md` (M1) + M2 checks. Read them.

## Outcome
The remaining matrix-gap scenarios on the Sisypy harness, cross-scenario synthesis restored, a `COVERAGE.md` matrix, and — now that M3 parity is proven and M4 net-new scenarios run — the legacy bespoke harness decommissioned.

## Scope (IN)
Build these net-new scenarios (YAML + brief + assessment):
1. **`cross_pack_authoring`** [Authoring×Compose] — author a NEW orchestrator composing executors from two DIFFERENT packs (e.g. editorial.transcribe → foley.foley_review); assert discovery of both via search, DSL authoring, `author check`/compile pass.
2. **`broken_authoring_fix`** [Authoring×Repair, adversarial] — an existing orchestrator has a compile-breaking DSL bug; agent runs `author check`, reads the error, fixes, recompiles clean.
3. **`no_tool_exists_pushback`** [Discovery×Refuse] — ask for a capability with NO registry match; agent searches with ≥2-3 query formulations, concludes nothing matches, pushes back instead of hallucinating a tool id (assert via U1 claim-vs-evidence + a "did-not-fabricate" enforced check).
4. **`discover_projects_runs_sessions`** [Discovery×Infra] — agent discovers existing projects/runs/sessions via `projects ls`/`runs ls`/`sessions ls` before acting.
5. **`author_run_revise_loop`** [Authoring×Execute, M/L] — author → run → observe wrong output → revise the DSL.
6. **`recover_from_no_search_results`** [Discovery×Recover] — first search returns zero hits; agent rephrases/broadens/`list`-falls-back rather than concluding "none" after one query.
7. (Optional, budget permitting) **`ambiguous_brief_clarification`** [Execution×Refuse] — underspecified brief; agent asks a clarifying question rather than guessing.

Plus:
- **Cross-scenario synthesis** — restore the `pattern_finder`-equivalent: read-only post-run synthesis over every scenario's summary/aggregate, surfacing recurring friction patterns. Wire to Sisypy's native cross-run synthesis if it exists (confirm in `sisypy/`), else a thin Astrid-side script over the new evidence-pack format.
- **`tests/agentic/COVERAGE.md`** — render the Domain×Challenge matrix with every scenario (M3 migrated + M4 + M5) in its cell; empty cells explicitly labeled (e.g. "requires live GPU — out of scope").
- **Decommission the legacy harness** — now that M3 parity + M4/M5 coverage exist, delete or reduce to documented shims: legacy `runner.py`/`auditor.py`/`assessor.py`/`capture.py`/`universal_checks.py`. `git grep` must show no live import of the old path. Preserve `_validate_rubrics.py` semantics if still relevant.

## Locked decisions
- M2 checks apply automatically; these scenarios add scenario-specific items only.
- Discovery scenarios assert the RIGHT path from evidence (a `search`/`list` call BEFORE authoring/execution; ≥2 query formulations before a no-results pushback).
- Decommission only AFTER confirming the Sisypy path covers what each removed module did.

## Open questions for the planner
- Brief wording for `no_tool_exists_pushback`/`recover_from_no_search_results` that reliably has no registry match yet is plausible.
- Whether Sisypy provides native cross-run synthesis or the legacy `pattern_finder.py` logic must be ported.
- A small orchestrator for `author_run_revise_loop` that runs structurally and yields an observably-wrong-then-fixed output.

## Constraints
- Structural mode: no network/GPU/spend.
- Synthesis is read-only over frozen reports; never mutates evidence or gates a scenario.

## Done criteria
- All new scenarios load and structurally pass.
- Synthesis runs over a multi-scenario structural sweep and emits a report.
- `tests/agentic/COVERAGE.md` places every scenario in the matrix; empty cells labeled.
- Legacy harness removed/shimmed; `git grep` clean; full suite runs end-to-end via the Sisypy path.

## Touchpoints
- `tests/agentic/scenarios/` + `briefs/` (new), synthesis script, `tests/agentic/COVERAGE.md`, removal of legacy modules. Read-only: `astrid/core/orchestrator/*`, `astrid/packs/*`, `sisypy/`.

## Anti-scope
- Do NOT modify `astrid/` production code or fix filed discoverability tickets — scenarios probe/expose.
- Do NOT build live-GPU/Reigh/RunPod or Supabase-sync scenarios — out of scope; note as future work in COVERAGE.md.
- Do NOT change M1/M2 contracts non-additively.
