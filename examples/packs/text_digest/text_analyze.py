"""Author-scaffolded orchestrator: text_digest.text_analyze.

Edit the steps below to describe your task. Run:
  astrid orchestrate check text_digest.text_analyze
  astrid orchestrate compile text_digest.text_analyze
  astrid orchestrate describe text_digest.text_analyze
"""

from __future__ import annotations

from astrid.orchestrate import (
    code,
    file_nonempty,
    orchestrator,
)


@orchestrator("text_digest.text_analyze")
def text_analyze():
    return [
        # TODO: replace with the real executor argv and produces.
        code(
            "step_one",
            argv=["python3", "-m", "astrid", "executors", "run", "<pack>.<executor>"],
            produces={"out": file_nonempty()},
        ),
    ]
