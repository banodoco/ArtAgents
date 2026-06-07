"""Legacy task-mode probe orchestrator used by regression tests."""

from __future__ import annotations

from astrid.orchestrate import attested, orchestrator, repeat_for_each
from astrid.verify import json_file


@orchestrator("builtin.agent_probe")
def agent_probe():
    return [
        attested(
            "per_item",
            command="echo '{\"verdict\":\"ship\"}' > verdict.json",
            instructions=(
                "Review the current probe item and write verdict.json with "
                'a JSON object containing "verdict", then approve. '
                "Context: $ASTRID_TASK_PROJECT/$ASTRID_TASK_RUN_ID/"
                "$ASTRID_TASK_ITEM_ID."
            ),
            ack="agent",
            produces={"verdict": json_file()},
            repeat=repeat_for_each(items=["alpha", "beta", "gamma"]),
        ),
    ]
