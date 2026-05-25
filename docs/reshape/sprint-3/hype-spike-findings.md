# Hype Spike Findings - Sprint 3 Editor-Review Repeat

**Spike fixture:** `.tmp/sprint3_hype_editor_review_spike.py`
**Generated evidence:** `.tmp/sprint3_hype_editor_review_spike/`
**Status:** tested. The editor-review loop is expressible with group `repeat.until` resolving a descendant produce through `re_export`. No schema redesign stop-line tripped.

## Tested Shape

The spike modelled the minimal Hype spine needed for the Sprint 3 schema lock:

```text
transcribe -> cut -> render -> editor_review
```

`editor_review` is a group step carrying the repeat:

```json
{
  "id": "editor_review",
  "children": [
    {
      "id": "review",
      "adapter": "manual",
      "command": "editor-review",
      "requires_ack": true,
      "produces": {
        "verdict": {
          "path": "editor_review.json",
          "check": {"check_id": "file_nonempty", "params": {}, "sentinel": false}
        }
      }
    },
    {
      "id": "refine",
      "adapter": "local",
      "command": "python -m astrid.packs.builtin.refine",
      "produces": {
        "patch": {
          "path": "refine.patch.json",
          "check": {"check_id": "file_nonempty", "params": {}, "sentinel": false}
        }
      }
    }
  ],
  "repeat": {
    "until": "editor_review.produces.verdict.status == \"approved\"",
    "max_iterations": 2,
    "on_exhaust": "escalate"
  },
  "re_export": {
    "verdict": "review.produces.verdict"
  }
}
```

The descendant artifact is written at the versioned iteration path:

```text
steps/editor_review/review/v1/iterations/001/produces/editor_review.json
steps/editor_review/review/v1/iterations/002/produces/editor_review.json
```

The group expression intentionally references `editor_review.produces.verdict`, not `editor_review.review.produces.verdict`. The group boundary owns the public produce name and resolves it through `re_export` to the descendant leaf.

## Spike Result

Command:

```bash
PYTHONPATH=. python3 .tmp/sprint3_hype_editor_review_spike.py
```

Observed result:

```json
{
  "expression": "editor_review.produces.verdict.status == \"approved\"",
  "first_iteration_result": false,
  "second_iteration_result": true,
  "missing_data_fails_closed": true,
  "group_re_export": {"verdict": "review.produces.verdict"}
}
```

The first fixture wrote `{"status": "revise"}` and evaluated false. The second fixture wrote `{"status": "approved"}` and evaluated true. A missing third-iteration artifact raised during resolution, so the runtime can fail closed instead of treating missing data as approval.

Production validation now accepts this expression grammar. Before the Sprint 3
implementation landed, the same fixture failed with the enum-era error:

```text
TaskPlanError: plan steps[3].repeat.until must be one of 'user_approves','verifier_passes','quorum', got 'editor_review.produces.verdict.status == "approved"'
```

That rejection is now migration-history context only; new plans should use the
expression form below.

## Locked Grammar

Sprint 3 should implement only the grammar the spike exercised:

```text
until:   <ref> <op> <literal>
ref:     <step-path>.produces.<name>[.<json-field>*]
op:      == | != | in
literal: JSON string | number | boolean | null | JSON array for in
```

Reference rules:

- `step-path` is a dot-separated path from the plan root.
- If `step-path` points at a leaf, `<name>` must be a declared produce on that leaf.
- If `step-path` points at a group, `<name>` must be present in the group's `re_export` map and resolve to a descendant `<child-path>.produces.<name>`.
- JSON field traversal after the produce name is runtime-only. Schema validation can prove the produce exists, but it cannot prove arbitrary fields inside the future JSON payload.
- Literals use JSON syntax. Strings are double-quoted in plan JSON, e.g. `"approved"` inside the expression string.

Boolean composition (`and`, `or`, parentheses) is out of scope for Sprint 3. The editor-review loop only needs one comparison.

## Runtime Implications

- `repeat.until` must be legal on group and leaf steps.
- The cursor should evaluate the expression after each completed iteration of the repeated host.
- Evaluation must read the produced JSON from the current iteration's versioned step directory. For the tested group shape, that means resolving the group alias to `steps/editor_review/review/v1/iterations/<NNN>/produces/editor_review.json`.
- Missing files, malformed JSON, missing fields, unresolved `re_export`, and unsupported operators must fail closed. They should not advance the repeat as satisfied.
- `max_iterations` and `on_exhaust` remain the exhaustion controls.
- New v2 plans should not special-case legacy conditions such as `user_approves`, `verifier_passes`, or `quorum`. Those strings belong only in migration/read compatibility.

## Schema And Validator Implications

- `RepeatUntil.condition` must change from a literal enum to a parsed expression string.
- Plan validation should parse the expression and reject malformed grammar.
- Static validation should resolve the step path and produce name where knowable.
- For group references, validation must follow `re_export`; a group does not auto-aggregate descendant produces.
- Mutation validation must run the same expression and `re_export` checks as initial plan validation.
- Existing `re_export` stays group-only. The spike confirms that explicit re-export is the right boundary for descendant produces and avoids implicit aggregation ambiguity.

## Decision

Use this final loop shape:

```text
editor_review.repeat.until =
  editor_review.produces.verdict.status == "approved"

editor_review.re_export.verdict =
  review.produces.verdict
```

This is enough for Hype's editor-review repeat loop, keeps descendant implementation details behind the group boundary, and gives Step 4 a narrow grammar to implement and test.
