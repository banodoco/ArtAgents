# Agentic tests

A test class distinct from the rest of the suite. These tests run a real LLM
(Claude / DeepSeek) through a real Astrid workflow and score what it
*experienced*, not just what the code returned.

The point: **prompts, skill docs, error messages, and discovery surfaces
are interfaces.** Unit tests can't tell you "this instruction is confusing
to an LLM" or "the agent rolled their own pipeline because they couldn't
find `video_editing.hype`." Agentic tests can.

## When to run

| Layer | When | Cost |
|---|---|---|
| Programmatic (rest of `tests/`) | Every commit | Free / fast |
| Agentic | Before merging UX-affecting changes; on release branch nightly | $-$$ per scenario |

Don't run on every commit — these are expensive.

## How to run

The **Sisypy-backed runner** is the primary entry point. It delegates to
[Sisypy](https://pypi.org/project/sisypy/) for execution, assessment, and
reporting while using the Astrid adapter for project lifecycle management.

```bash
# Single scenario (skip name to run all 36 production scenarios)
python -m tests.agentic.runner cold_restart

# Structural smoke test (no real actor dispatch)
python -m tests.agentic.runner _smoke --actor fake --mode structural

# With a specific actor and report tag
python -m tests.agentic.runner vague_video_request --actor hermes --tag v9

# Sisypy help (all supported flags)
python -m tests.agentic.runner --help
```

Legacy flags (`--all`, `--tier`, `--agent`, `--only`, `--timeout`,
`--budget`, `--run-tag`) are rejected with a migration message directing
you to the Sisypy equivalents. The legacy runner (`runner_legacy.py`)
and parallel runner (`parallel_runner.py`) were decommissioned in M5.

Results land in `tests/agentic/reports/<date>-<tag>/` with one markdown
per agent + a `summary.json` aggregating pass/fail by acceptance criterion.</

## What a scenario looks like

Scenarios are **data, not code** — YAML files under `scenarios/`. The
contract is small enough that an agent can add a new one without editing
Python (the meta-test verifies this).

```yaml
name: vague_video_request
tier: discovery
description: |
  Agent receives an open-ended request ("make a video from this footage")
  and must discover `video_editing.hype` rather than rolling their own pipeline.
priming:
  - create_project: ${SLUG}
brief: vague_video_request.md
agents:
  - model: deepseek-v4-pro
    count: 1
    subagent_type: general-purpose
target_orchestrator: video_editing.hype
acceptance:
  - tool_used: video_editing.hype
  - subjective:
      - discovered_via_orchestrators_list_or_search
      - read_pack_skill_before_running
      - did_not_reinvent_pipeline_from_scratch
budget:
  max_tokens_per_agent: 32768
  max_wall_clock_min: 15
assessment:
  enforced:
    - id: invoked_via_canonical_cli
      question: |
        Did the agent invoke via `astrid orchestrators run`?
      evidence: [stderr]
      grading: pass_fail
      weight: 2
  graded:
    - id: discovered_via_orchestrators_list_or_search
      question: |
        Did the agent discover `video_editing.hype` via `astrid orchestrators search`?
      evidence: [stderr]
      grading: pass_fail
      weight: 2
    - id: did_not_reinvent_pipeline_from_scratch
      question: |
        Did the agent avoid building their own ffmpeg pipeline?
      evidence: [stderr, report]
      grading: pass_fail
      weight: 2
  observed:
    - id: shell_calls_count
      question: "How many shell calls did the agent make?"
      evidence: [stderr]
      grading: numeric
      weight: 0
extras:
  target_orchestrator: video_editing.hype
  legacy_acceptance:
    - tool_used: video_editing.hype
    - subjective:
        - discovered_via_orchestrators_list_or_search
        - read_pack_skill_before_running
        - did_not_reinvent_pipeline_from_scratch
  universal_checks: true
  m2_checks:
    c3_no_mutation_on_read:
      enabled: true
```

The `acceptance:` block carries legacy criteria. The **executable**
rubric lives under the scenario's `assessment:` block (consumed by
Sisypy). The `extras:` block carries mirrored copies
(`legacy_acceptance`, `target_orchestrator`, `universal_checks`) for
backward compatibility. See
[SCENARIO_MIGRATION.md](SCENARIO_MIGRATION.md) for the full per-scenario
mapping.

## Assessment pipeline (Sisypy, v6+)

Sisypy handles enforcement assessment directly via the `assessment:`
block in each scenario YAML. The deterministic check layers (universal
enforcement, M2 integrity, M5 behavior) run via the adapter's
`project_universal_checks()` against a frozen evidence pack at
`reports/<date>-<tag>-<scenario>/evidence/<slug>/`, captured by the
adapter post-actor and containing `report.md`, `stderr.log`,
`runs/*/events.jsonl`, `tree.txt`, `plan.json` (when present), and
`.astrid-session` (when present).

1. **Sisypy assessment** (primary): `assessment.enforced` (hard
   pass/fail), `assessment.graded` (LLM-evaluated rubric), and
   `assessment.observed` (telemetry, weight 0). Sisypy's internal
   evaluator runs these automatically during the run.

2. **Universal enforcement** (`tests/agentic/enforcement.py`,
   deterministic Python, enabled via `extras.universal_checks: true`):
   - `_check_canonical_bypass` — flags reaching a pack via
     `python -m astrid.packs.X.run`, `from astrid.packs.X import`,
     `import astrid.packs.X`, or a direct `astrid/packs/X/run.py`
     path. Scenarios that legitimately create new packs can set
     `assessment.bypass_exempt: true` to opt out.
   - `deliverable_shape` — verifies `report.md` exists, has ≥30
     non-blank lines, and contains each numbered section the brief
     asked for (heading-, bold-, or bullet-numbered).

3. **M2 integrity checks** (`tests/agentic/checks/`): deterministic
   evidence-level checks (no_mutation_on_read, projection_fidelity,
   append_not_rewrite, idempotent_reattach) dispatched via
   `extras.m2_checks`.

4. **M5 behavior checks** (`tests/agentic/checks/m5_scenarios.py`):
   deterministic textual-analysis checks (refusal, search fallback,
   infrastructure discovery, author-check looping, cross-pack
   discovery, author-run-revise fallback) dispatched via
   `extras.m5_checks`.

5. **Cross-scenario synthesis** (`tests/agentic/synthesis.py`):
   read-only deterministic CLI that scans Sisypy evidence packs and
   aggregates outcomes. Emits `synthesis.md` + `synthesis.json`.
   Not auto-invoked by the runner — human triggers post-run.

## Tiers

Scenarios are tagged by tier so you can run a focused subset:

| Tier | Purpose | Examples |
|---|---|---|
| `core` | Hardened — should always pass | cold_restart, sequential_orchestrators |
| `discovery` | Skill-trigger + pack-finding | vague_video_request, transcribe_audio |
| `authoring` | Creating new orchestrators/executors/elements | new_orchestrator_from_dsl, wrap_comfy_workflow |
| `recovery` | Failure handling | verifier_reject, takeover_stalled |
| `forensics` | Debug an already-failed run | why_did_run_fail |
| `meta` | Tests the agentic test infra itself | write_new_scenario |

`core` is the regression set. Everything else is exploration.

## Reading a report

`reports/<date>-<tag>-<scenario>/summary.json` looks like (v6 schema):

```json
{
  "scenario": "vague_video_request",
  "agents": [
    {
      "slug": "ds_a",
      "model": "deepseek-v4-pro",
      "passed": true,
      "criteria": { "events_contain.run_completed": {"passed": true, "ungraded": false}, "...": "..." },
      "universal": {
        "contradictions": [],
        "canonical_path_bypass": false,
        "deliverable_shape": { "ok": true, "missing_sections": [], "line_count": 47, "required_sections": [1,2,3,4] }
      },
      "assessor": {
        "verdicts": { "discovered_via_orchestrators_list_or_search": {"passed": true, "rationale": "...", "evidence_refs": ["stderr:..."], "confidence": 1.0}, "...": "..." },
        "contradictions": [],
        "overall_passed": true,
        "summary": "All rubric checks pass.",
        "model": "deepseek-chat",
        "elapsed_sec": 7.85
      },
      "evidence_pack": "tests/agentic/reports/.../evidence/ds_a"
    }
  ],
  "aggregate": {
    "passed": 2,
    "total": 3,
    "by_criterion": {"events_contain.run_completed": [true, true, false], "...": "..."}
  },
  "friction_patterns": []
}
```

If an agent record is missing an `assessor` block, the scenario YAML
had no `assessment:` block (legacy). If the assessor record has
`ungraded: true`, the run was soft-skipped (most commonly: no
`DEEPSEEK_API_KEY` available). In both cases the agent's `passed`
flag still reflects the machine criteria — the assessor adds
signal, it doesn't replace the existing pass/fail surface.

Friction patterns are the *signal* — same shape across multiple agents
indicates a system gap, not an agent quirk. That's what drives the next
round of fixes.

## When you add a new scenario

1. Drop a YAML under `scenarios/` matching the schema in
   `scenarios/_schema.yaml` and the conventions in
   [SCENARIO_MIGRATION.md](SCENARIO_MIGRATION.md).
2. Drop the brief template under `briefs/` (variables: `${SLUG}`,
   `${AGENT_ID}`, `${RUN_TAG}`, `${TARGET_ORCH}`).
3. Add the orchestrator(s) under `astrid/packs/builtin/` if it's new
   (or reference an existing one).
4. Run it: `python -m tests.agentic.runner <name>`.
5. Inspect the report; if the scenario is stable, add it to the `core`
   tier.

The meta-scenario (`write_new_scenario`) tests whether an *agent* can
do this without hand-holding. If they can't, the schema or docs are wrong.

## What this is NOT

- **Not unit tests.** No `assert ==` against return values.
- **Not integration tests** in the conventional sense. There's nothing
  deterministic to assert.
- **Not benchmarks.** We're not measuring model capability; we're
  measuring system UX.
- **Not a substitute for `tests/test_*.py`.** Those still run on every
  commit. Agentic tests are an *additional* surface.

## Design philosophy

Three principles:

1. **Friction surfaces, not pass/fail.** A scenario that "passes" but
   takes 30 shell calls + 3 retries is still a friction signal worth
   acting on. Look at the patterns across agents, not just the bottom-
   line verdict.

2. **Cross-model variance is data.** If Claude completes cleanly but
   DeepSeek struggles on the same scenario, the system is leaning on
   model-specific instinct. That's a real signal — fix the prompt /
   skill / error message so both models succeed identically.

3. **Each new test exposes a design question.** Don't pre-decide which
   solution to ship for a UX gap. Write the test that would expose the
   gap; run it; let the failure pattern dictate the fix.
