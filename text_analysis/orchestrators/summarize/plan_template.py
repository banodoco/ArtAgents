# text_analysis.summarize — plan v2 template
#
# This file defines ``build_plan_v2``, the function that produces the plan
# dict emitted by the orchestrator runner.  Import helpers from
# ``astrid.core.orchestrator.plan_template`` so you don't need to copy-paste the
# emit / step-command / produces boilerplate into your pack.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrid.core.orchestrator.plan_template import (
    emit_plan_json,
    build_step_command,
    make_produces,
)


def build_plan_v2(
    *,
    python_exec: str,
    run_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return a minimal valid plan-v2 dict.

    This stub produces a single ``adapter: local`` step.  Replace the
    placeholder command and expand the step list to match your pipeline.
    """
    run_root = Path(run_root)

    # TODO: replace this placeholder with your real step command.
    # Use ``build_step_command`` or construct the command string directly.
    step_id = "hello"
    command = f"{python_exec} -c 'print(\"hello from {qualified_id}\")' --out {run_root}/steps/{step_id}/v1/produces"

    plan: dict[str, Any] = {
        "plan_id": "text_analysis.summarize",
        "version": 2,
        "steps": [
            {
                "id": step_id,
                "adapter": "local",
                "command": command,
                "produces": {
                    # TODO: replace with your real produces path(s).
                    "hello_output": {
                        "path": "hello.txt",
                        "check": {
                            "check_id": "file_nonempty",
                            "params": {},
                            "sentinel": False,
                        },
                    }
                },
            }
        ],
    }
    return plan


if __name__ == "__main__":
    # Quick smoke-test: build a plan and emit it to a temp path.
    import tempfile

    run_root = Path(tempfile.mkdtemp(prefix="plan-test-"))
    plan = build_plan_v2(python_exec=sys.executable, run_root=run_root)
    plan_path = run_root / "plan.json"
    emit_plan_json(plan, plan_path)
    print(f"plan emitted to {plan_path}")
