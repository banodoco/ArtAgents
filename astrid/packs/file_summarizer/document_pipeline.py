"""Author-scaffolded orchestrator: file_summarizer.document_pipeline.

Three-step pipeline that:
  1. Reads a small text file from disk (code step).
  2. Writes a summary JSON describing the text (attested step).
  3. Writes a one-line verdict (nested step wrapping a code step).

Run:
  astrid author check file_summarizer.document_pipeline
  astrid author compile file_summarizer.document_pipeline
  astrid author describe file_summarizer.document_pipeline
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
    "file_summarizer.document_pipeline.verdict",
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
                    "json.dump({'status': 'ok', 'verdict': 'text pipeline completed successfully'}, "
                    "open(out, 'w'))"
                ),
            ],
            produces={"verdict.json": file_nonempty()},
        ),
    ],
)


@orchestrator("file_summarizer.document_pipeline")
def document_pipeline():
    return [
        # Step 1: Read a small text file from disk and stage it.
        code(
            "read_input",
            argv=[
                "python3",
                "-c",
                (
                    "import os, shutil; "
                    "src = os.environ.get('ASTRID_TASK_INPUT_TEXT') "
                    "or 'astrid/packs/file_summarizer/fixtures/document_pipeline/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # Step 2: Summarize the staged text (attested step).
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

        # Step 3: Verdict — one-line JSON emitted by a nested code step.
        nested(
            "verdict",
            plan=_VERDICT_SUBPLAN,
        ),
    ]
