"""Author-scaffolded orchestrator: text_review.file_audit.

Three-step pipeline that:
  1. reads a small text file from disk (code step),
  2. writes a summary JSON describing the text (code step — auto-generated),
  3. writes a one-line verdict (attested step — agent-curated).

Step kinds: code -> code -> attested.

Run:
  astrid author check text_review.file_audit
  astrid author compile text_review.file_audit
  astrid author describe text_review.file_audit
"""

from __future__ import annotations

from astrid.orchestrate import (
    attested,
    code,
    file_nonempty,
    json_file,
    orchestrator,
)


@orchestrator("text_review.file_audit")
def file_audit():
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
                    "or 'examples/packs/text_review/fixtures/file_audit/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # Step 2: Auto-generate a summary JSON describing the text.
        # This code step counts lines, words, characters, and derives
        # metadata directly — no agent attestation needed.
        code(
            "auto_summarize",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os, sys; "
                    "produces_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "project = os.environ['ASTRID_TASK_PROJECT']; "
                    "run_id = os.environ['ASTRID_TASK_RUN_ID']; "
                    "projects_root = os.environ['ASTRID_PROJECTS_ROOT']; "
                    "input_path = os.path.join(projects_root, project, 'runs', "
                    "run_id, 'steps', 'read_input', 'v1', 'produces', 'input.txt'); "
                    "with open(input_path) as f: "
                    "    text = f.read(); "
                    "lines = text.splitlines(); "
                    "words = text.split(); "
                    "summary = {"
                    "    'line_count': len(lines), "
                    "    'word_count': len(words), "
                    "    'char_count': len(text), "
                    "    'avg_word_len': round(sum(len(w) for w in words) / max(len(words), 1), 2), "
                    "    'first_line': lines[0] if lines else '', "
                    "    'preview': text[:200]"
                    "}; "
                    "os.makedirs(produces_dir, exist_ok=True); "
                    "json.dump(summary, open(os.path.join(produces_dir, 'summary.json'), 'w'), indent=2)"
                ),
            ],
            produces={"summary.json": json_file()},
        ),

        # Step 3: Agent writes a one-line verdict (attested).
        attested(
            "write_verdict",
            command="echo write_verdict",
            instructions=(
                "Review the auto-generated summary at:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/auto_summarize/v1/produces/summary.json\n\n"
                "Write a one-line JSON verdict to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_verdict/v1/produces/verdict.json\n\n"
                'Shape: {"verdict": "<one-line assessment>"}\n'
                "The verdict is a single JSON object with one key 'verdict' "
                "giving your one-line take on the input text.\n"
                "Ack when done."
            ),
            ack="agent",
            produces={
                "verdict.json": json_file(),
            },
        ),
    ]
