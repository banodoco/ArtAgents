# M2 — Migrate the 29 existing scenarios onto Sisypy

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§6 migration mapping) and `tests/agentic/ADAPTER.md` (produced by M1 — the adapter API + evidence-pack + universal-checks contract). Read both before planning.

## Outcome
All 29 existing agentic scenarios run on the Sisypy harness embedded in M1, with their acceptance criteria expressed in Sisypy's `assessment: {enforced, graded, observed}` model, and the bespoke `runner.py`/`auditor.py`/`assessor.py` removed (or reduced to thin shims). The structural (fake-actor) run of every migrated scenario passes the harness's own well-formedness gate.

## Scope (IN)
- Port each of the 29 `tests/agentic/scenarios/*.yaml` to the Sisypy scenario schema. The existing scenarios ALREADY use `assessment: {enforced, graded, observed}` and machine criteria (`events_contain`, `no_aborts`, `tool_used`, `leaf_count_complete`, `no_cross_project_binding`, `shell_calls_under`) — map per design §6:
  - `events_contain`/`no_aborts`/`tool_used`/`leaf_count_complete` → adapter-parsed event-kind/plan checks, expressed as enforced criteria + proof-ladder level.
  - `shell_calls_under` → `observed` (telemetry, never gates).
  - `no_cross_project_binding` → `enforced` (now also covered by universal check #10).
  - Fold redundant `subjective:` blocks into `assessment.rubric` (the superset validator already requires every subjective key to have a rubric question).
- Carry over the briefs under `tests/agentic/briefs/` (variable substitution `$SLUG`/`$AGENT_ID`/`$RUN_TAG`/`$TARGET_ORCH` must keep working through Sisypy's brief templating — adapt the adapter's prime hook if needed).
- Preserve priming (`create_project`, `start`, `ack`, `write`, `touch`, `env`, `start_with_plan`) via the M1 adapter prime hook.
- Decommission the bespoke harness: delete or shim `runner.py` (legacy), `auditor.py`, `assessor.py`, `universal_checks.py`, `capture.py`, `pattern_finder.py` — their behavior is now the Sisypy runner + M1 adapter universal checks. Keep `_validate_rubrics.py` semantics (every subjective/rubric key validated) if still relevant.
- Update `tests/agentic/README.md` to describe the Sisypy-based flow.

## Locked decisions
- 1:1 where the schema already matches (assessment tiers, budget, tags, agents).
- Universal checks live in the adapter (M1), NOT re-declared per scenario.
- Tiering preserved: `core` is the regression set; everything else is exploration. Map existing `tier:` values to Sisypy's tier field.

## Open questions for the planner
- Dispatch: existing scenarios use `model: claude | deepseek-v4-pro | kimi-k2p5` with `count` and `subagent_type`. Confirm how Sisypy's actor/dispatcher model expresses the hermes-subagent path (DeepSeek/Kimi) and the Claude Agent-tool path; the adapter/runner may need a dispatcher shim. In structural CI the fake actor is used regardless — real-actor dispatch parity can be validated lightly.
- Whether any existing criterion has NO clean Sisypy equivalent and needs a small adapter capability rather than a schema field.

## Constraints
- Every migrated scenario must pass a **structural** (fake-actor) run — i.e. the harness can load it, prime it, capture an evidence pack, and run checks without a live model. This is the objective gate for this milestone.
- No behavior regression in what each scenario asserts: the same contract that was enforced before must remain enforced (or be strictly strengthened by a universal check).

## Done criteria
- `python -m tests.agentic.runner --all --actor fake --mode structural` loads and structurally passes all 29.
- The bespoke harness modules are gone or reduced to documented shims; `git grep` shows no live import of the old auditor/assessor from the new path.
- README reflects the new flow.
- A migration note lists, per scenario, old-criterion → Sisypy-construct (the audit trail).

## Touchpoints
- `tests/agentic/scenarios/*.yaml`, `tests/agentic/briefs/*.md`, `tests/agentic/README.md`, the bespoke `*.py` modules, the M1 adapter/runner.

## Anti-scope
- Do NOT add net-new scenarios (M3/M4).
- Do NOT change the M1 adapter contract except additively (if a migrated scenario truly needs a new adapter capability, add it without breaking M1's smoke test, and note it).
- Do NOT touch `astrid/` production code.
