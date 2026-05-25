"""Author-scaffolded orchestrator: file_summarizer.e2e_text_pipeline.

End-to-end text pipeline that:
  1. reads a small text file from disk (code step),
  2. writes a summary JSON describing the text (attested step),
  3. writes a one-line verdict (attested step).

Run:
  astrid author check file_summarizer.e2e_text_pipeline
  astrid author compile file_summarizer.e2e_text_pipeline
  astrid author describe file_summarizer.e2e_text_pipeline
"""

from __future__ import annotations

from astrid.orchestrate import (
    attested,
    code,
    file_nonempty,
    json_file,
    orchestrator,
)


@orchestrator("file_summarizer.e2e_text_pipeline")
def e2e_text_pipeline():
    return [
        # Step 1: Read a small text file from disk and stage it in produces/.
        code(
            "read_input",
            argv=[
                "python3",
                "-c",
                (
                    "import os, shutil; "
                    "src = os.environ.get('ASTRID_TASK_INPUT_TEXT') "
                    "or 'examples/packs/file_summarizer/fixtures/e2e_text_pipeline/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # Step 2: Write a summary JSON describing the text (attested).
        attested(
            "write_summary",
            command="echo write_summary",
            instructions=(
                "Read the input text from:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/read_input/v1/produces/input.txt\n\n"
                "Analyze the text and write a summary JSON to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_summary/v1/produces/summary.json\n\n"
                "The JSON shape must be:\n"
                "{\n"
                '  "line_count": <int>,\n'
                '  "word_count": <int>,\n'
                '  "char_count": <int>,\n'
                '  "notes": "<one sentence describing the text>"\n'
                "}\n\n"
                "Count actual lines, words, and characters from the input file.\n"
                "Write the summary then ack."
            ),
            ack="agent",
            produces={
                "summary.json": json_file(),
            },
        ),

        # Step 3: Write a one-line verdict as JSON (attested).
        attested(
            "write_verdict",
            command="echo write_verdict",
            instructions=(
                "Review the summary at:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_summary/v1/produces/summary.json\n\n"
                "Write a one-line JSON verdict to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_verdict/v1/produces/verdict.json\n\n"
                "Shape: {\"verdict\": \"<one-line assessment>\"}\n"
                "The verdict should be a single sentence assessing the text.\n"
                "Ack when done."
            ),
            ack="agent",
            produces={
                "verdict.json": json_file(),
            },
        ),
    ]
