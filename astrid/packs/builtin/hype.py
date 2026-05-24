"""Canonical hype orchestrator used by the Phase 9 author-test smoke fixture.

The legacy ``builtin.hype`` lived under ``builtin/hype/`` as a Stage-based
runtime; this sibling ``hype.py`` is the DSL-flavored orchestrator the author
test path replays. ``compile.resolve_orchestrator`` loads it via
``spec_from_file_location`` so the file/folder coexist without import
collision.
"""

from __future__ import annotations

from astrid.orchestrate import attested, code, json_file, orchestrator


@orchestrator("builtin.hype")
def hype():
    return [
        code("noop", argv=["python3", "-c", "print('ok')"]),
        attested(
            "review",
            command="echo review",
            instructions="approve to finish",
            ack="human",
        ),
        attested(
            "verdict",
            command="echo '{\"verdict\": \"ship\"}' > verdict.json",
            instructions=(
                "Write a one-line JSON verdict to verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"ship\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "verdict.json")},
        ),
        attested(
            "final_verdict",
            command="echo '{\"verdict\": \"ship\"}' > final_verdict.json",
            instructions=(
                "Write a one-line JSON verdict to final_verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"ship\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "final_verdict.json")},
        ),
        attested(
            "closing_verdict",
            command="echo 'ship' > verdict.txt",
            instructions=(
                "Write a one-line verdict to verdict.txt (e.g. 'ship'), "
                "then ack to finish."
            ),
            ack="human",
        ),
        attested(
            "end_verdict",
            command="echo 'ready' > end_verdict.txt",
            instructions=(
                "Write a one-line verdict to end_verdict.txt (e.g. 'ready'), "
                "then ack to finish."
            ),
            ack="human",
        ),
        attested(
            "terminal_verdict",
            command="echo '{\"verdict\": \"complete\"}' > terminal_verdict.json",
            instructions=(
                "Write a one-line JSON verdict to terminal_verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"complete\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "terminal_verdict.json")},
        ),
        attested(
            "ultimate_verdict",
            command="echo '{\"verdict\": \"done\"}' > ultimate_verdict.json",
            instructions=(
                "Write a one-line JSON verdict to ultimate_verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"done\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "ultimate_verdict.json")},
        ),
        attested(
            "concluding_verdict",
            command="echo 'done' > concluding_verdict.txt",
            instructions=(
                "Write a one-line verdict to concluding_verdict.txt (e.g. 'done'), "
                "then ack to finish."
            ),
            ack="human",
        ),
        attested(
            "final_review",
            command="echo '{\"verdict\": \"complete\"}' > final_review.json",
            instructions=(
                "Write a one-line JSON verdict to final_review.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"complete\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "final_review.json")},
        ),
        attested(
            "wrap_verdict",
            command="echo '{\"verdict\": \"ship\"}' > wrap_verdict.json",
            instructions=(
                "Write a one-line JSON verdict to wrap_verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"ship\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "wrap_verdict.json")},
        ),
        attested(
            "attested_final",
            command="echo 'ship' > verdict.txt",
            instructions=(
                "Write a one-line verdict to verdict.txt (e.g. 'ship'), "
                "then ack to finish."
            ),
            ack="human",
        ),
        attested(
            "agentic_append_verdict",
            command="echo '{\"verdict\": \"ship\"}' > agentic_append_verdict.json",
            instructions=(
                "Write a one-line JSON verdict to agentic_append_verdict.json with a single "
                "\"verdict\" key (e.g. {\"verdict\": \"ship\"}), then ack to finish."
            ),
            ack="human",
            produces={"verdict": (json_file(), "agentic_append_verdict.json")},
        ),
    ]
