"""Author-scaffolded orchestrator: text_digest.quick_review.

Three-step pipeline that:
  1. reads a small text file from disk (code step),
  2. writes a summary JSON describing the text (attested step),
  3. writes a one-line verdict (code step).

Step kinds: code → attested → code (no nested sub-plans).

Run:
  astrid orchestrate check text_digest.quick_review
  astrid orchestrate compile text_digest.quick_review
  astrid orchestrate describe text_digest.quick_review
"""

from __future__ import annotations

from astrid.core.orchestrate import (
    attested,
    code,
    file_nonempty,
    json_schema,
    orchestrator,
)


@orchestrator("text_digest.quick_review")
def quick_review():
    return [
        # 1) Read a small text file from disk and stage it in produces/.
        code(
            "read_input",
            argv=[
                "python3",
                "-c",
                (
                    "import os, shutil; "
                    "src = os.environ.get('ASTRID_TASK_INPUT_TEXT') "
                    "or 'examples/packs/text_digest/fixtures/quick_review/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # 2) Summarize the staged text. Attested — an agent inspects the
        #    file, writes summary.json with counts + notes, then acks.
        attested(
            "summarize_text",
            command="echo summarize_text",
            instructions=(
                "Read the text staged at "
                "$ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/"
                "$ASTRID_TASK_RUN_ID/steps/read_input/v1/produces/input.txt\n"
                "Write a summary JSON to "
                "$ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/"
                "$ASTRID_TASK_RUN_ID/steps/summarize_text/v1/produces/"
                "summary.json\n"
                "Shape: {\"line_count\": <int>, \"word_count\": <int>, "
                "\"char_count\": <int>, \"notes\": \"<one sentence>\"}.\n"
                "Then run `astrid ack` to advance."
            ),
            ack="agent",
            produces={
                "summary.json": json_schema(
                    {
                        "type": "object",
                        "required": [
                            "line_count",
                            "word_count",
                            "char_count",
                            "notes",
                        ],
                        "properties": {
                            "line_count": {"type": "integer"},
                            "word_count": {"type": "integer"},
                            "char_count": {"type": "integer"},
                            "notes": {"type": "string"},
                        },
                    }
                ),
            },
        ),

        # 3) Verdict — a code step that writes a one-line verdict JSON.
        code(
            "write_verdict",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "out = os.path.join(os.environ['ASTRID_TASK_PRODUCES_DIR'], "
                    "'verdict.json'); "
                    "json.dump({'verdict': 'text processed successfully'}, "
                    "open(out, 'w'))"
                ),
            ],
            produces={"verdict.json": file_nonempty()},
        ),
    ]
