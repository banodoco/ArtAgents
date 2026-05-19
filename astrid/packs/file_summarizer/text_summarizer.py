"""Author-scaffolded orchestrator: file_summarizer.text_summarizer.

Reads a small text file from disk, writes a summary JSON describing the text,
then writes a one-line verdict.

Run:
  astrid author check file_summarizer.text_summarizer
  astrid author compile file_summarizer.text_summarizer
  astrid author describe file_summarizer.text_summarizer
"""

from __future__ import annotations

from astrid.orchestrate import code, attested, orchestrator, json_file, file_nonempty


@orchestrator("file_summarizer.text_summarizer")
def text_summarizer():
    return [
        # Step 1: Read a small text file from disk.
        code(
            "read_file",
            argv=["python3", "-c", (
                "import json,sys,os; "
                "project=os.environ['ASTRID_TASK_PROJECT']; "
                "run_id=os.environ['ASTRID_TASK_RUN_ID']; "
                "step_dir=f'$ASTRID_PROJECTS_ROOT/{project}/runs/{run_id}/steps/read_file/v1'; "
                "os.makedirs(f'{step_dir}/produces', exist_ok=True); "
                "os.makedirs(f'{step_dir}/inputs', exist_ok=True); "
                "with open(f'{step_dir}/inputs/input.txt', 'w') as f: f.write('The quick brown fox jumps over the lazy dog. This is a sample text for testing the Astrid orchestrator pipeline.'); "
                "print('input written')"
            )],
            produces={"input_file": file_nonempty()},
        ),
        # Step 2: Write a summary JSON describing the text.
        attested(
            "write_summary",
            command="echo write_summary",
            instructions=(
                "Read the input text from:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/read_file/v1/inputs/input.txt\n\n"
                "Analyze the text and write a summary JSON to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_summary/v1/produces/summary.json\n\n"
                "The JSON shape must be:\n"
                "{\n"
                '  "character_count": <int>,\n'
                '  "word_count": <int>,\n'
                '  "sentence_count": <int>,\n'
                '  "language": "en",\n'
                '  "top_words": ["<word1>", "<word2>", "<word3>"],\n'
                '  "sentiment": "<positive|neutral|negative>"\n'
                "}\n\n"
                "Write the summary then ack."
            ),
            ack="actor",
            produces={
                "summary.json": json_file(),
            },
        ),
        # Step 3: Write a one-line verdict as JSON.
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
                "The verdict should be a single JSON object with one key 'verdict' "
                "assessing whether the input text was interesting or useful.\n"
                "Ack when done."
            ),
            ack="actor",
            produces={
                "verdict.json": json_file(),
            },
        ),
    ]
