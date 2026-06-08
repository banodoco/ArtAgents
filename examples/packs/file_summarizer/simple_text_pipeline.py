"""Author-scaffolded orchestrator: file_summarizer.simple_text_pipeline.

Three-step pipeline that:
  1. Reads a small text file from disk (code step).
  2. Writes a summary JSON describing the text (attested step).
  3. Writes a one-line plain-text verdict (code step).

Run:
  astrid orchestrate check file_summarizer.simple_text_pipeline
  astrid orchestrate compile file_summarizer.simple_text_pipeline
  astrid orchestrate describe file_summarizer.simple_text_pipeline
"""

from __future__ import annotations

from astrid.core.orchestrate import (
    attested,
    code,
    file_nonempty,
    json_file,
    orchestrator,
)


@orchestrator("file_summarizer.simple_text_pipeline")
def simple_text_pipeline():
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
                    "or 'examples/packs/file_summarizer/fixtures/simple_text_pipeline/input.txt'; "
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

        # Step 3: Write a one-line plain-text verdict (code step).
        code(
            "write_verdict",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "summary_path = os.path.join("
                    "os.environ['ASTRID_PROJECTS_ROOT'], "
                    "os.environ['ASTRID_TASK_PROJECT'], 'runs', "
                    "os.environ['ASTRID_TASK_RUN_ID'], 'steps', "
                    "'write_summary', 'v1', 'produces', 'summary.json'); "
                    "summary = json.load(open(summary_path)); "
                    "verdict = ("
                    "'PASS' if summary.get('word_count', 0) > 3 "
                    "else 'NEEDS_MORE_WORDS'); "
                    "out_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(out_dir, exist_ok=True); "
                    "with open(os.path.join(out_dir, 'verdict.txt'), 'w') as f: "
                    "f.write(verdict + '\\n')"
                ),
            ],
            produces={"verdict.txt": file_nonempty()},
        ),
    ]
