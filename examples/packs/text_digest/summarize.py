"""Author-scaffolded orchestrator: text_digest.summarize.

Three-step pipeline that:
  1. reads a small text file from disk (code step),
  2. writes a JSON summary describing the text (attested step),
  3. emits a one-line verdict (nested wrapper around a code step).

Run:
  astrid orchestrate check text_digest.summarize
  astrid orchestrate compile text_digest.summarize
  astrid orchestrate describe text_digest.summarize
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


# Sub-plan referenced by the top-level `verdict` nested step. Splitting
# the verdict into its own plan exercises the `nested(plan=_PlanBuilder)`
# branch of the DSL.
_VERDICT_SUBPLAN = plan(
    "text_digest.summarize.verdict",
    [
        code(
            "write_verdict",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os, sys; "
                    "out = os.path.join(os.environ['ASTRID_TASK_PRODUCES_DIR'], "
                    "'verdict.json'); "
                    "json.dump({'ok': True, 'message': 'summary written'}, "
                    "open(out, 'w'))"
                ),
            ],
            produces={"verdict.json": file_nonempty()},
        ),
    ],
)


@orchestrator("text_digest.summarize")
def summarize():
    return [
        # 1) Read a small text file from disk and stage it in produces/.
        #    Path is the env-supplied source `ASTRID_TASK_INPUT_TEXT` and
        #    falls back to a repo-local sample when unset so the step can be
        #    exercised end-to-end without extra wiring.
        code(
            "read_input",
            argv=[
                "python3",
                "-c",
                (
                    "import os, shutil, sys; "
                    "src = os.environ.get('ASTRID_TASK_INPUT_TEXT') "
                    "or 'examples/packs/text_digest/fixtures/summarize/input.txt'; "
                    "dst_dir = os.environ['ASTRID_TASK_PRODUCES_DIR']; "
                    "os.makedirs(dst_dir, exist_ok=True); "
                    "shutil.copyfile(src, os.path.join(dst_dir, 'input.txt'))"
                ),
            ],
            produces={"input.txt": file_nonempty()},
        ),

        # 2) Summarize the staged text. Attested because an agent (or human)
        #    has to inspect the file, compose meaningful counts/notes, and
        #    only then attest the JSON it wrote.
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

        # 3) Verdict — one-line file emitted by a tiny inline code step
        #    wrapped in a nested sub-plan. Exercises kind=nested with an
        #    inline _PlanBuilder reference (not a string qid).
        nested(
            "verdict",
            plan=_VERDICT_SUBPLAN,
        ),
    ]
