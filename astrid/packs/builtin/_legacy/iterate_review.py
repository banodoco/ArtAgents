"""Realistic-shape test orchestrator: write-then-revise with iteration.

Mirrors the shape of refine / editor_review patterns: agent writes a draft,
a verifier judges, agent iterates based on feedback until it passes or hits
max iterations. The probe target: does the agent actually READ the verifier's
rejection and incorporate it, or does it just retry the same artifact?

The hard part of this pattern in real packs is that each iteration writes to
its own ``iterations/NNN/produces/`` directory, and the agent has to thread
the prior iteration's rejection into the new attempt.
"""

from __future__ import annotations

from astrid.orchestrate import attested, orchestrator, repeat_until
from astrid.verify import json_schema


@orchestrator("builtin.iterate_review")
def iterate_review():
    return [
        # 1. Initial draft. No iteration; one shot.
        attested(
            "draft",
            command="echo draft",
            instructions=(
                "Write a one-paragraph proposal for a new Astrid skill called "
                "'astrid checkpoint' (hypothetical) that lets agents bookmark "
                "intermediate run state. The proposal must include three required "
                "fields:\n"
                "  - \"name\": the verb name\n"
                "  - \"behavior\": one sentence describing what it does\n"
                "  - \"failure_mode\": one sentence describing how it can fail\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/draft/v1/produces/proposal.json\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "proposal.json": json_schema(
                    {
                        "type": "object",
                        "required": ["name", "behavior", "failure_mode"],
                        "properties": {
                            "name": {"type": "string"},
                            "behavior": {"type": "string"},
                            "failure_mode": {"type": "string"},
                        },
                    }
                ),
            },
        ),

        # 2. Iterate-until-user-approves. Each iteration writes to
        # iterations/NNN/produces/. The probe is: does the agent
        # incorporate prior-iteration feedback explicitly?
        attested(
            "revise",
            command="echo revise",
            instructions=(
                "Revise the proposal from `draft` step to add operator-facing "
                "concerns: rollback path, audit-ledger impact, and one named "
                "antagonist who would misuse this feature.\n"
                "Each iteration writes to its OWN directory:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/revise/v1/iterations/NNN/produces/revision.json\n"
                "(where NNN is the iteration index, zero-padded to 3 digits, e.g. 001).\n"
                "The schema requires: rollback, audit_impact, named_antagonist, "
                "incorporates_prior_feedback. The last field MUST be \"none\" on "
                "iteration 001, and on later iterations must literally quote the "
                "prior iteration's feedback (read from iterations/NNN-1/feedback.txt).\n"
                "Ack with `--decision approve` to ship, or `--decision iterate "
                "--feedback \"<text>\"` to request another pass (feedback is written "
                "as the next iteration's input). Max 3 iterations."
            ),
            ack="agent",
            produces={
                "revision.json": json_schema(
                    {
                        "type": "object",
                        "required": [
                            "rollback",
                            "audit_impact",
                            "named_antagonist",
                            "incorporates_prior_feedback",
                        ],
                        "properties": {
                            "rollback": {"type": "string"},
                            "audit_impact": {"type": "string"},
                            "named_antagonist": {"type": "string"},
                            "incorporates_prior_feedback": {"type": "string"},
                        },
                    }
                ),
            },
            repeat=repeat_until(
                "user_approves",
                max_iterations=3,
                on_exhaust="escalate",
            ),
        ),

        # 3. Finalize. Combines draft + last revision into shippable form.
        attested(
            "finalize",
            command="echo finalize",
            instructions=(
                "Read the draft and the final revision (last iteration that was "
                "acked with approve):\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/draft/v1/produces/proposal.json\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/revise/v1/iterations/<last-approved>/produces/revision.json\n"
                "Produce a shippable summary at:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/finalize/v1/produces/spec.json\n"
                "Shape: {\"name\": \"<str>\", \"summary\": \"<paragraph>\", "
                "\"iterations_used\": <int>, \"final_verdict\": \"ship\"}.\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "spec.json": json_schema(
                    {
                        "type": "object",
                        "required": ["name", "summary", "iterations_used", "final_verdict"],
                        "properties": {
                            "name": {"type": "string"},
                            "summary": {"type": "string"},
                            "iterations_used": {"type": "integer", "minimum": 1},
                            "final_verdict": {"type": "string", "enum": ["ship"]},
                        },
                    }
                ),
            },
        ),
    ]
