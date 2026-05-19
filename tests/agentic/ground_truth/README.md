# Ground truth — hand-graded reference verdicts

The `<scenario>.expected.json` files in this directory are the
hand-graded reference verdicts the assessor (`assessor.py`) is
calibrated against by `meta_test.py`.

## Schema

Each file matches the assessor output schema's `verdicts` sub-object:

```json
{
  "scenario": "<name>",
  "evidence_pack": "<relative path the human read>",
  "verdicts": {
    "<question_id>": {
      "passed": true | false | null,
      "note": "<short rationale referencing evidence>"
    }
  },
  "overall_passed": true | false,
  "graded_by": "POM",
  "graded_at": "<ISO date>"
}
```

`passed=null` is reserved for genuinely ungradable questions (evidence
missing). It is NOT a "soft pass" — meta_test treats null and a
non-matching assessor verdict equally.

## Scenarios chosen

Three representative scenarios, picked to cover the three failure-mode
families the rubric is most likely to confuse:

1. **specific_transcribe** — canonical-path-heavy. The agent's report
   sounds successful but quotes `python3 -m astrid.packs.builtin.transcribe.run`
   in the dry-run step, raising the question of whether the final
   invocation went via the canonical CLI. Tests whether the assessor
   distinguishes "discovered canonically" from "invoked canonically".

2. **cold_restart_midrun** — narrative-heavy. The agent succeeded but
   the recovery path was friction-laden (`astrid next --agent` failed,
   takeover required `--force`). Tests whether the assessor reads the
   narrative carefully enough to grade the path, not just the outcome.

3. **sequential_orchestrators** — structural. The agent's two runs both
   reached `run_completed` (events show this) but the agent emitted a
   zero-byte report. Tests whether the assessor distinguishes
   "task achieved" from "deliverable shape intact".

## Use

Read each report.md + stderr.log + events.jsonl under
`tests/agentic/reports/20260518-115105-<scenario>/evidence/<slug>/`,
then update the corresponding `.expected.json` if rubric questions
change.
