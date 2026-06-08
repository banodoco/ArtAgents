"""Legacy author-test DSL shim for ``video_editing.hype``."""

from __future__ import annotations

from astrid.core.orchestrate import attested, code, orchestrator
from astrid.core.verify import json_file


def _json_verdict_step(step_id: str, filename: str, verdict: str) -> object:
    return attested(
        step_id,
        command=f"echo '{{\"verdict\": \"{verdict}\"}}' > {filename}",
        instructions=(
            f"Write a one-line JSON verdict to {filename} with a single "
            f'"verdict" key (e.g. {{"verdict": "{verdict}"}}), then ack to finish.'
        ),
        ack="human",
        produces={"verdict": (json_file(), filename)},
    )


def _text_verdict_step(step_id: str, filename: str, verdict: str) -> object:
    return attested(
        step_id,
        command=f"echo '{verdict}' > {filename}",
        instructions=(
            f"Write a one-line verdict to {filename} (e.g. '{verdict}'), then ack to finish."
        ),
        ack="human",
    )


@orchestrator("video_editing.hype")
def hype() -> list[object]:
    return [
        code("noop", argv=["python3", "-c", "print('ok')"]),
        attested(
            "review",
            command="echo review",
            instructions="approve to finish",
            ack="human",
        ),
        _json_verdict_step("verdict", "verdict.json", "ship"),
        _json_verdict_step("final_verdict", "final_verdict.json", "ship"),
        _text_verdict_step("closing_verdict", "verdict.txt", "ship"),
        _text_verdict_step("end_verdict", "end_verdict.txt", "ready"),
        _json_verdict_step("terminal_verdict", "terminal_verdict.json", "complete"),
        _json_verdict_step("ultimate_verdict", "ultimate_verdict.json", "done"),
        _text_verdict_step("concluding_verdict", "concluding_verdict.txt", "done"),
        _json_verdict_step("final_review", "final_review.json", "complete"),
        _json_verdict_step("wrap_verdict", "wrap_verdict.json", "ship"),
        _text_verdict_step("attested_final", "verdict.txt", "ship"),
        _json_verdict_step("agentic_append_verdict", "agentic_append_verdict.json", "ship"),
    ]
