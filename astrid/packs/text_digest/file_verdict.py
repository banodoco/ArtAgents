"""Author-scaffolded orchestrator: text_digest.file_verdict.

Three-step pipeline that:
  1. reads a small text file from disk (code step),
  2. writes a JSON summary describing the text (attested step),
  3. emits a one-line verdict (nested code step).

Run:
  astrid author check text_digest.file_verdict
  astrid author compile text_digest.file_verdict
  astrid author describe text_digest.file_verdict
"""

from __future__ import annotations

from astrid.orchestrate import (
    attested,
    code,
    file_nonempty,
    json_schema,
    nested,
    orchestrator,
    plan,
)


# Sub-plan for the verdict step: a single code step that writes verdict.json
_VERDICT_SUBPLAN = plan(
    "text_digest.file_verdict.verdict",
    [
        code(
            "emit_verdict",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "out = os.path.join(os.environ['ASTRID_TASK_PRODUCES_DIR'], "
                    "'verdict.json'); "
                    "json.dump({'status': 'ok', 'verdict': 'text processed successfully'}, "
                    "open(out, 'w'))"
                ),
            ],
            produces={"verdict.json": file_nonempty()},
        ),
    ],
)


@orchestrator("text_digest.file_verdict")
def file_verdict():
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
                    "or 'astrid/packs/text_digest/fixtures/file_verdict/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # 2) Summarize the staged text. Attested — an agent inspects the text
        #    and writes the summary JSON.
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

        # 3) Verdict — one-line JSON file emitted by a tiny inline code step
        #    wrapped in a nested sub-plan.
        nested(
            "verdict",
            plan=_VERDICT_SUBPLAN,
        ),
    ]
