# M3 — Convert the 29 existing scenarios to Sisypy schema (legacy harness kept as fallback)

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` §6 and the FROZEN `tests/agentic/ADAPTER.md` (M1) + check battery (M2). Read them. NOTE (review correction): this is a SCHEMA-CONVERSION sprint, not a trivial 1:1 port — the substitution syntax and runner flags differ.

## Outcome
All 29 existing scenarios expressed in Sisypy's schema and runnable structurally on the M1/M2 harness, with the universal+conditional checks (M2) applied to each. The legacy harness is KEPT as a working fallback this milestone — decommission is deferred to M5 after parity is proven.

## Scope (IN)
- Convert each `tests/agentic/scenarios/*.yaml` to the Sisypy scenario schema. Specifics the review flagged:
  - Brief variable substitution changes from `$VAR` (legacy) to **`${VAR}`** (Sisypy runner) — update every brief reference (`$SLUG`→`${SLUG}`, etc.). Confirm against `sisypy/runner.py`.
  - Astrid scenarios ALREADY use `assessment: {enforced, graded, observed}` — Sisypy uses the SAME three-tier model. KEEP it. Do NOT fold into an `assessment.rubric` key (Sisypy has no `rubric` key — that was a mistaken instruction).
  - Map legacy `acceptance:` machine criteria (`events_contain`, `no_aborts`, `tool_used`, `leaf_count_complete`, `no_cross_project_binding`, `shell_calls_under`) into Sisypy `enforced`/`observed` items backed by the M2 checks where one exists (e.g. `no_cross_project_binding` → U4; chain assertions → U3). `shell_calls_under` → `observed`.
  - There is NO `--all` flag in the Sisypy runner — omitting scenario names means "all". Update README/run examples accordingly (confirm against `sisypy/runner.py`).
- Carry over briefs under `tests/agentic/briefs/`; ensure priming still works through the M1 adapter prime hook.
- Preserve tiering (`core` regression set vs exploration) via Sisypy's tier field.
- Update `tests/agentic/README.md` to describe the Sisypy flow (correct substitution + run syntax).

## Locked decisions
- 1:1 where schema already matches (enforced/graded/observed, budget, tags, agents, tiers).
- Universal/conditional checks live in the adapter (M2), NOT re-declared per scenario; a scenario only adds scenario-specific (S1/S2) or extra enforced/graded items.
- Legacy harness stays runnable; both paths coexist until M5.

## Open questions for the planner
- Confirm Sisypy's exact substitution + per-scenario field names against `sisypy/schema.py` and `sisypy/runner.py` before bulk-converting (a single wrong field name breaks all 29).
- Whether any legacy criterion has no Sisypy/M2 equivalent and needs a small additive adapter capability.
- Dispatcher parity for `model: claude|deepseek-v4-pro|kimi-k2p5` with `count`/`subagent_type` (structural CI uses fake actor regardless; real-actor parity validated lightly).

## Constraints
- Every converted scenario must pass a STRUCTURAL (fake-actor) load+prime+capture+checks run — the objective gate.
- No weakening of any contract a scenario previously enforced (universal checks may strengthen it).

## Done criteria
- All 29 load and structurally pass on the Sisypy runner (no-name = all, fake actor, structural mode).
- README reflects the new `${VAR}` substitution and the name-less "all" run form.
- A migration note maps, per scenario, legacy-criterion → Sisypy construct / M2 check.
- Legacy harness still runs (fallback intact).

## Touchpoints
- `tests/agentic/scenarios/*.yaml`, `tests/agentic/briefs/*.md`, `tests/agentic/README.md`, the M1/M2 adapter+runner. Read-only: `sisypy/schema.py`, `sisypy/runner.py`.

## Anti-scope
- Do NOT decommission or delete the legacy harness (that is M5).
- Do NOT build net-new scenarios (M4/M5).
- Do NOT change the M1 ADAPTER.md contract or M2 checks non-additively.
- Do NOT modify `astrid/` production code or Sisypy.
