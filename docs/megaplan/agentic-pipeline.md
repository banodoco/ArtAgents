# Astrid agentic assessment pipeline — sprint brief

**Profile:** `partnered` (tier 3, full robustness, low depth, default vendor).

## Goal

Build a 3-layer automated pipeline that turns the existing `tests/agentic/`
scaffolding into a **rigorously self-assessing** test suite. Today the
pipeline runs actor sub-agents and grades their work with shallow machine
criteria — that's why v5 had multiple "passed but didn't really" cases
(empty deliverables, narrative claims unsupported by stderr, agents
bypassing the canonical CLI surface). We're closing that gap.

The principle: **the test is the loop (brief → actor → assessment), not
just the actor's behavior.** Weak assessment = weak test, regardless of
how good the actor was. So the work isn't "fix the tests" — it's "make
assessment as strong as the actions being assessed."

The pipeline we're building is **also a prototype of Astrid's production
runtime evaluation surface.** When a real agent reports "done, 6 steps
completed," Astrid has the same problem we're solving here: was that
true? The assessor we build doubles as that primitive.

## Architecture

```
Layer 1 (actor):   brief + priming → narrative + stderr + project state
                                        ↓
Layer 1.5 (capture):                 evidence_pack/  (snapshot bundle on disk)
                                        ↓
Layer 2a (machine):                  auditor verdicts (deterministic, existing)
                                        ↓
Layer 2b (universal):                contradictions + canonical-bypass + shape
                                        ↓
Layer 2c (assessor):                 per-scenario rubric verdict (LLM)
                                        ↓
Layer 3 (pattern-finder):            cross-scenario friction report (LLM)
                                        ↓
                                     summary.json + run-<ts>.md
```

## File structure

```
tests/agentic/
├── runner.py              # existing — actor dispatch (extend: invoke capture)
├── capture.py             # NEW — post-run evidence snapshot
├── auditor.py             # existing — machine criteria
├── universal_checks.py    # NEW — contradiction, canonical-bypass, deliverable
├── assessor.py            # NEW — rubric-driven LLM grader
├── pattern_finder.py      # NEW — cross-scenario synthesis
├── meta_test.py           # NEW — assessor vs hand-graded ground truth
├── scenarios/*.yaml       # ADD `assessment:` block per scenario (13 files)
├── ground_truth/          # NEW — hand-graded reports for calibration
│   ├── README.md
│   └── *.expected.json
└── reports/<ts>-<sc>/
    ├── *.report.md
    ├── *.stderr.log
    ├── evidence/<slug>/   # NEW — full project snapshot
    │   ├── plan.json
    │   ├── runs/*/events.jsonl
    │   ├── .astrid-session
    │   ├── current_run.json
    │   └── tree.txt
    └── summary.json       # extended schema (see below)
```

## Locked design decisions

1. **Assessor model: DeepSeek V4 Pro** via the official DeepSeek API
   (`https://api.deepseek.com/v1/chat/completions`), same path as the
   `subagent-launcher` skill's pathway 3. Dispatch from Python with the
   `openai` SDK pointed at the DeepSeek base URL (or `requests` directly
   — both work; OpenAI-compatible interface). Reads `DEEPSEEK_API_KEY`
   from `~/.hermes/.env`. Use `temperature=0.0`,
   `response_format={"type": "json_object"}` for structured output,
   `max_tokens=16384` (DeepSeek is a reasoning model — reasoning tokens
   count against the budget; smaller caps return empty content).
   **Trade-off vs the original Claude Haiku design**: actor and assessor
   share the same model family. We accept the shared-blindspot risk
   because: (a) the rubric questions are structured factual checks
   against an evidence pack, not open-ended judgment; (b) the
   `universal_checks` layer (contradiction detection, canonical-path
   bypass, deliverable shape) runs on raw evidence in deterministic
   Python and catches anything the assessor might cooperatively
   overlook; (c) the user has DEEPSEEK_API_KEY available, while
   ANTHROPIC_API_KEY is not configured on this machine; (d) for Phase 6
   meta-test, if we find shared-blindspot patterns, the model can be
   swapped to Kimi K2.5 (via FIREWORKS_API_KEY in `~/.hermes/.env`,
   same dispatch shape) with a one-line config change.

2. **Evidence pack lives on disk**, not memory. Reusable across reruns of
   the assessor without rerunning the actor. Debuggable.

3. **Temperature 0.0 on assessor and pattern-finder.** Same evidence →
   same verdict. Verdict drift would confound regression signal.

4. **N=1 actor per scenario in Phase 1–6**; generalize to N=3 in Phase 7
   if assessor calibration is solid. Don't bake in concurrency before
   the assessment quality is proven.

5. **Read-only pipeline output.** Never auto-files tickets, never
   auto-dispatches fix sub-agents. The human reads the run-`<ts>`.md
   and decides. Auto-action stays gated until meta-test confirms
   reliability over multiple runs.

6. **The pipeline is locally runnable**, not CI-integrated. Wall-clock
   per full run is ~80 min — too slow for pre-commit. CI integration
   is deferred.

## Rubric YAML schema (locked)

Every scenario gains an `assessment:` block alongside the existing
`acceptance:` block. The new block does NOT replace `acceptance:` —
machine criteria still run; the rubric is additional, richer signal.

```yaml
assessment:
  # Opt into the universal cross-cutting checks. Default true.
  universal_checks: true

  # Per-scenario rubric questions. 5–10 per scenario.
  rubric:
    - id: <snake_case_id>             # stable handle for verdict aggregation
      question: |                     # plain-English question, multi-line OK
        Did the agent X?
      evidence: [stderr, report, events, project_tree]   # which parts of the
                                       # evidence pack the assessor should read
      grading: pass_fail               # pass_fail | pass_fail_partial
      weight: 1                        # 1 = standard, 2 = canonical-path or
                                       # correctness-grade question
      failure_mode: |                  # what failure looks like — anchors
        The agent grep'd source files instead of using `astrid X search`.
```

Worked example for `specific_transcribe`:

```yaml
assessment:
  universal_checks: true
  rubric:
    - id: discovered_via_canonical_search
      question: |
        Did the agent discover `builtin.transcribe` via the canonical CLI
        path (`astrid executors search transcribe` or `astrid executors
        list`), as opposed to grepping source files or reading
        astrid/packs/ directly?
      evidence: [stderr, report]
      grading: pass_fail_partial
      weight: 1
      failure_mode: |
        Stderr shows `grep transcribe astrid/packs/...` or
        `find astrid/packs/ -name '*transcribe*'` BEFORE any
        `astrid executors search` invocation.

    - id: invoked_via_canonical_cli
      question: |
        Did the agent invoke the tool via `astrid executors run
        builtin.transcribe ...`, as opposed to
        `python -m astrid.packs.builtin.executors.transcribe.run ...` or
        a direct import?
      evidence: [stderr]
      grading: pass_fail
      weight: 2

    - id: did_not_install_own_whisper
      question: |
        Did the agent avoid pip-installing `openai-whisper`, writing a
        one-off `openai.audio.transcriptions` wrapper, or shelling out
        to `whisper` directly?
      evidence: [stderr]
      grading: pass_fail
      weight: 1

    - id: report_shape_intact
      question: |
        Does the report contain all 4 numbered sections the brief asked
        for (What you did, What tools you discovered, Discoverability
        notes, Biggest UX gap), each with at least one non-empty
        sentence?
      evidence: [report]
      grading: pass_fail
      weight: 1

    - id: produced_transcript_artifact
      question: |
        Did the run produce a `transcript.json` (or `.srt` / `.txt`) on
        disk under the project's `runs/` tree or the `--out` directory
        the agent chose?
      evidence: [project_tree]
      grading: pass_fail
      weight: 1
```

## Universal checks (locked)

Three functions in `universal_checks.py`, run against every scenario
regardless of rubric:

1. **`detect_contradictions(evidence)`** — extract every concrete
   factual claim from the narrative ("I ran X", "It produced Y",
   "Completed N steps"). For each, search stderr/events/artifacts
   for supporting evidence. Emit a list of `{claim, evidence_against,
   severity}` records. **Severity = major** if claim asserts an action
   that didn't happen (false invocation, false count, false output).

2. **`canonical_path_bypass(evidence)`** — scan stderr for
   `python -m astrid\.packs\.[a-z_.]+\.run` invocations. If found AND
   the scenario's `target_orchestrator`/`target_executor` is one with a
   canonical `astrid <verb> run <id>` path, flag as bypass.

3. **`deliverable_shape(evidence, brief)`** — verify `report.md`
   exists, is ≥ 30 lines of non-whitespace content, and contains
   each section heading the brief's "Report back" section requested
   (regex match on `^#+\s*\d+\.\s*<heading>` or similar).

## Assessor prompt skeleton (locked)

The assessor's per-question prompt structure is the system's contract.
Locking it here so implementation has a target.

```
SYSTEM
You are an evaluator for the Astrid agentic test pipeline. You read the
evidence pack from an actor sub-agent and grade it against a rubric.
Every verdict must be supported by *direct quoted evidence* from the
pack. Hallucination is the failure mode — if evidence is missing for a
question, return verdict=null (ungraded) with a rationale. Never grade
"pass" by default.

Output JSON only. No prose. No preamble. No code fences.

USER
# Scenario
<brief.md verbatim>

# Rubric
<JSON-encoded list of question objects from the scenario YAML>

# Evidence pack

## report.md
<verbatim>

## stderr.log
<filtered to [tool]/[done] lines + any line containing "exit "
or "error" or "rejected" — capped at 8000 chars from each end if longer>

## events.jsonl (all runs in this project, concatenated)
<verbatim, capped at 4000 chars>

## project tree
<find ... -type f, capped at 200 lines>

## plan.json (if present)
<verbatim, capped at 4000 chars>

## .astrid-session (if present)
<verbatim>

# Output schema (strict JSON)

{
  "verdicts": {
    "<question_id>": {
      "passed": true | false | null,         // null = ungraded
      "rationale": "<one to three sentences quoting evidence>",
      "evidence_refs": ["stderr:lines-N-M", "report:section-2", ...],
      "confidence": 0.0
    }
  },
  "contradictions": [
    {
      "claim": "<exact quote from narrative>",
      "evidence_against": "<exact quote from stderr/events>",
      "severity": "minor" | "major"
    }
  ],
  "overall_passed": true | false,
  "summary": "<≤200 chars>"
}

# Rules
1. Quote evidence verbatim — don't paraphrase.
2. Missing evidence → passed=null, not passed=true.
3. Contradictions are first-class signal. Flag any narrative claim that
   evidence directly refutes, even if no rubric question targets it.
4. overall_passed = (all rubric verdicts weight-passed) AND (no major
   contradictions). A single null verdict on a weight=2 question fails.
5. Confidence reflects evidence strength, not your own certainty about
   the topic.
```

The assessor function signature:

```python
def assess(
    evidence_pack: Path,           # path to reports/<ts>-<sc>/evidence/<slug>/
    rubric: dict,                  # parsed `assessment:` block from scenario YAML
    brief_text: str,               # the brief.md the actor saw
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """Returns the structured verdict dict per the output schema above."""
```

## summary.json schema extension

Existing fields stay. New fields:

```json
{
  "scenario": "...",
  "tier": "...",
  "agents": [
    {
      "slug": "...",
      "model": "...",
      "passed": true,
      "criteria": { ... },          // existing machine criteria
      "universal": {                // NEW
        "contradictions": [...],
        "canonical_path_bypass": false,
        "deliverable_shape": true
      },
      "assessor": {                 // NEW
        "verdicts": { ... },
        "overall_passed": true,
        "summary": "...",
        "model": "claude-haiku-4-5",
        "elapsed_sec": 4.2
      }
    }
  ],
  "aggregate": { ... }
}
```

## Phasing

**Phase 1 — Capture layer** (~3 hrs, no LLM).
Build `capture.py`. Hook into runner.py to bundle the evidence pack
post-run. Verify by inspecting one snapshot end-to-end against a fresh
runner invocation of `specific_transcribe`.

**Phase 2 — Universal checks** (~4 hrs, no LLM).
Implement the three functions in `universal_checks.py`. Wire into
`auditor.audit_scenario`. Re-audit the v5 reports (reports under
`tests/agentic/reports/20260518-115105-*`) to verify which previously-
passing scenarios now correctly fail.

**Phase 3 — One-scenario rubric prototype** (~half day).
Pick `specific_transcribe` (rubric already drafted above). Build
`assessor.py` with the Anthropic SDK. Iterate until verdict matches
an attentive-human grade on the v5 evidence pack.

**Phase 4 — Rubric rollout** (~half day).
Author `assessment:` blocks for the other 12 scenarios. Run assessor
against all 15 v5 evidence packs. Spot-check ~3 verdicts by hand.

**Phase 5 — Pattern-finder** (~half day).
Build `pattern_finder.py`. Takes the directory of summary.json files
plus the evidence packs. Dispatches a single Claude call with the
same prompt structure used in this session's v5 manual analysis.
Produces `run-<ts>.md` headlining the dogfood verdict.

**Phase 6 — Meta-test** (~half day).
Hand-grade 3 historical reports into `ground_truth/<scenario>.expected.json`.
Build `meta_test.py` that compares assessor output to ground truth on a
per-question basis. Tune rubric questions for disagreements. Publish a
calibration report — "assessor agreed with ground truth on N/M questions
at C confidence threshold."

**Phase 7 — v6 dogfood** (~80 min wall-clock + post-run analysis).
End-to-end run with the full pipeline. Read run-`<ts>`.md. Compare its
synthesis quality to the v5 manual analysis. Note any false-pass or
false-fail cases.

## Out of scope (do not do)

- CI integration (deferred).
- Auto-filing tickets from pattern-finder output (gated until trust).
- N=3 actors per scenario (Phase 7+ decision, not now).
- Switching assessor to Sonnet or higher (only if Haiku fails meta-test).
- Refactoring runner.py beyond what capture-layer integration requires.
- Subjective-criteria backward-compat: existing `subjective:` blocks in
  scenario YAMLs can stay as-is; the new `assessment:` block supersedes
  them and is the load-bearing surface.

## Acceptance criteria for this sprint

1. `tests/agentic/capture.py` exists; runner invokes it post-actor;
   evidence packs land under `reports/<ts>-<sc>/evidence/<slug>/`.
2. `tests/agentic/universal_checks.py` exists with the three documented
   functions; auditor calls them; summary.json's new `universal` block
   populates.
3. `tests/agentic/assessor.py` exists; calls Anthropic API at
   temperature=0; returns dict matching documented schema; auditor
   calls it; summary.json's new `assessor` block populates.
4. All 13 scenario YAMLs have an `assessment:` block with ≥ 5 rubric
   questions each.
5. `tests/agentic/pattern_finder.py` exists; reads all summary.json from
   a single dogfood run; produces `reports/<ts>/run.md`.
6. `tests/agentic/meta_test.py` exists; at least 3 hand-graded ground
   truth files exist; meta-test reports per-question agreement rate.
7. A full v6 dogfood completes end-to-end and produces `run.md` whose
   synthesis is comparable in quality to the v5 manual cross-report
   analysis (concrete metric: surfaces ≥ 5 of the 8 system gaps the
   v5 manual analysis surfaced).

## Operating notes

- **This sprint works on top of a substantial body of UNCOMMITTED local
  changes** in the working tree (auditor fixes, scenario fixes, v5 reports,
  and a long tail of unrelated session work). Do NOT stash, reset, or
  discard them. Read the working tree as it stands; the auditor fixes
  in `tests/agentic/auditor.py` and the scenario tightening in
  `tests/agentic/scenarios/*.yaml` are part of the starting state, not
  state to be undone. Last committed baseline is `036210b`; everything
  after that on disk is current session work and is load-bearing.
- The narrative-fallback widening in `_eval_tool_used` (in the
  uncommitted version of `auditor.py`) is a KNOWN soft spot — the
  assessor + universal checks replace its role, and the narrative
  fallback can be tightened back up once the assessor is online. Don't
  preemptively rip it out before Phase 3 lands.
- The existing `subjective:` blocks in scenario YAMLs are documentation
  of intent. The new `assessment:` block is the executable form. Where
  they overlap, the rubric should be a strict superset of the subjective
  intent (i.e. every subjective concern becomes a rubric question).
- The v5 evidence is reusable. We do NOT need to re-run actors to test
  Phases 1–5; we re-audit against the v5 reports already on disk
  (`tests/agentic/reports/20260518-115105-*`). Only Phase 7 needs a
  fresh actor run.
- Sub-agent dispatch from Python: prefer `anthropic` SDK directly over
  shelling out to `launch_hermes_agent.py`. The SDK gives structured
  output guarantees and cleaner error handling. The hermes launcher is
  for actor-tier work where the model needs tools.
