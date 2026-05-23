"""Author-scaffolded orchestrator: file_summarizer.clip_extract.

Edit the steps below to describe your task. Run:
  astrid author check file_summarizer.clip_extract
  astrid author compile file_summarizer.clip_extract
  astrid author describe file_summarizer.clip_extract
"""

from __future__ import annotations

from astrid.orchestrate import (
    code,
    file_nonempty,
    orchestrator,
)


@orchestrator("file_summarizer.clip_extract")
def clip_extract():
    return [
        # TODO: replace with the real executor argv and produces.
        code(
            "step_one",
            argv=["python3", "-m", "astrid", "executors", "run", "<pack>.<executor>"],
            produces={"out": file_nonempty()},
        ),
    ]
