# Agentic tests

A test class distinct from the rest of the suite. These tests run a real LLM
(Claude / DeepSeek) through a real Astrid workflow and score what it
*experienced*, not just what the code returned.

The point: **prompts, skill docs, error messages, and discovery surfaces
are interfaces.** Unit tests can't tell you "this instruction is confusing
to an LLM" or "the agent rolled their own pipeline because they couldn't
find `builtin.hype`." Agentic tests can.

## When to run

| Layer | When | Cost |
|---|---|---|
| Programmatic (rest of `tests/`) | Every commit | Free / fast |
| Agentic | Before merging UX-affecting changes; on release branch nightly | $-$$ per scenario |

Don't run on every commit — these are expensive.

## How to run

```bash
# Single scenario
python -m tests.agentic.runner cold_restart

# All scenarios in a tier
python -m tests.agentic.runner --tier discovery

# Full sweep (warning: $$, ~30 min wall-clock)
python -m tests.agentic.runner --all
```

### Parallel runner (process-per-scenario)

A separate CLI that runs multiple scenarios concurrently, each in its own
subprocess with filesystem isolation. Cuts wall-clock time for a full
sweep from ~80-90 min to ~12-15 min while keeping each scenario's
stdout, stderr, and project state in separate directories.

```bash
# Full sweep, 3 scenarios at a time (default)
python -m tests.agentic.parallel_runner --all --run-tag v8

# Specific scenarios, 2 at a time
python -m tests.agentic.parallel_runner specific_transcribe cold_restart_midrun --parallel 2 --run-tag v8

# Custom timeout (default: 1800s / 30 min per scenario)
python -m tests.agentic.parallel_runner --all --run-tag v8 --timeout 1200

# Clean up isolated dirs (dry-run; add --apply to actually delete)
python -m tests.agentic.parallel_runner --cleanup --run-tag v8
python -m tests.agentic.parallel_runner --cleanup --all --apply
```

Each scenario gets its own isolated `ASTRID_HOME` and
`ASTRID_PROJECTS_ROOT` under `/tmp/astrid-parallel-<tag>/<scenario>/`,
with per-scenario `logs/{stdout,stderr}.log`. Reports still land in the
shared `tests/agentic/reports/<tag>-<scenario>/` directory (no collision
risk because each child writes to its own scenario subdirectory). After
all children finish, `pattern_finder` is invoked automatically to
produce the cross-scenario synthesis.

The original sequential runner (`python -m tests.agentic.runner --all`)
is unchanged and still works.

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
  and must discover `builtin.hype` rather than rolling their own pipeline.
priming:
  - create_project: ${slug}
brief: vague_video_request.md
agents:
  - model: claude         # or deepseek-v4-pro
    count: 3              # parallel runs for variance
acceptance:
  - events_contain: run_completed
  - tool_used: builtin.hype
  - shell_calls_under: 40
  - no_aborts
  - subjective:                       # graded from the agent's narrative report
      - did_search_before_authoring
      - found_existing_pack
budget:
  max_tokens_per_agent: 32768
  max_wall_clock_min: 15
```

Each acceptance criterion is either **machine-graded** (parsed from
`events.jsonl` by the auditor) or **subjective**. The `subjective:`
block is **informational-only** as of the v6 pipeline — the
**executable** rubric lives under the scenario's `assessment:` block
(see "Assessment pipeline" below). The superset validator
(`tests/agentic/_validate_rubrics.py`) enforces that every subjective
key has a corresponding rubric question.

## Assessment pipeline (v6)

The auditor now runs three additional layers beyond the legacy
machine-criteria pass. All three read from a frozen evidence pack at
`reports/<date>-<tag>-<scenario>/evidence/<slug>/`, snapshotted by
`capture.py` post-actor and containing `report.md`, `stderr.log`,
`runs/*/events.jsonl`, `tree.txt`, `plan.json` (when present), and
`.astrid-session` (when present).

1. **Universal checks** (`tests/agentic/universal_checks.py`,
   deterministic Python):
   - `detect_contradictions` — extracts concrete narrative claims
     and flags any with no supporting trace in stderr / events /
     tree / plan.
   - `canonical_path_bypass` — flags reaching a pack via
     `python -m astrid.packs.X.run`, `from astrid.packs.X import`,
     `import astrid.packs.X`, or a direct `astrid/packs/X/run.py`
     path. Scenarios that legitimately create new packs can set
     `assessment.bypass_exempt: true` to opt out.
   - `deliverable_shape` — verifies `report.md` exists, has ≥30
     non-blank lines, and contains each numbered section the brief
     asked for (heading-, bold-, or bullet-numbered).

2. **Per-scenario rubric** (`tests/agentic/assessor.py`, DeepSeek
   V4 Pro via the OpenAI-compatible API at
   `https://api.deepseek.com/v1`). Each scenario YAML declares an
   `assessment:` block with `universal_checks: true` and a
   `rubric:` list of ≥5 questions. The assessor reads the evidence
   pack and returns `{verdicts, contradictions, overall_passed,
   summary, model, elapsed_sec}`. Missing
   `DEEPSEEK_API_KEY` → soft-skip with `ungraded: true`; key is
   read from `~/.hermes/.env` as a fallback.

3. **Cross-scenario synthesis** (`tests/agentic/pattern_finder.py`):
   human-invoked CLI that reads every `summary.json` under a
   dogfood run and dispatches a single DeepSeek call to surface
   recurring friction patterns. Writes `run.md` + `run.json` to
   `reports/<date>-<tag>-synthesis/`. Not auto-invoked by the
   runner — read-only synthesis the human triggers post-run.

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
   `scenarios/_schema.yaml`.
2. Drop the brief template under `briefs/` (variables: `$SLUG`,
   `$AGENT_ID`, `$ORCH`).
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
