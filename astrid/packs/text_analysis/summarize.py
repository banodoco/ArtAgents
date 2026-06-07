"""Orchestrator: text_analysis.summarize — read text, write summary JSON, write verdict.

A 3-step pipeline:
  1. read_input  — reads a text file from disk, writes content.json
  2. write_summary — aggregates metadata into summary.json
  3. write_verdict — emits a one-line verdict as verdict.json
"""

from __future__ import annotations

from astrid.orchestrate import (
    code,
    json_file,
    orchestrator,
)


@orchestrator("text_analysis.summarize")
def summarize():
    return [
        code(
            "read_input",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "p = os.environ.get('PRODUCES_ROOT', '{produces_root}'); "
                    "os.makedirs(p, exist_ok=True); "
                    "text = open('/Users/peteromalley/Documents/reigh-workspace/Astrid/astrid/packs/text_analysis/sample.txt').read(); "
                    "json.dump({'file': 'sample.txt', 'text': text, 'char_count': len(text), "
                    "'line_count': text.count(chr(10))}, "
                    "open(os.path.join(p, 'content.json'), 'w'))"
                ),
            ],
            produces={"content": (json_file(), "content.json")},
        ),
        code(
            "write_summary",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "p = os.environ.get('PRODUCES_ROOT', '{produces_root}'); "
                    "os.makedirs(p, exist_ok=True); "
                    "step_dir = os.path.dirname(os.path.dirname(p)); "
                    "prev = os.path.join(os.path.dirname(step_dir), 'read_input', 'v1', 'produces', 'content.json'); "
                    "content = json.load(open(prev)); "
                    "t = content['text']; "
                    "words = t.split(); "
                    "json.dump({'word_count': len(words), 'char_count': content['char_count'], "
                    "'line_count': content['line_count'], "
                    "'preview': t[:200] + '...' if len(t) > 200 else t}, "
                    "open(os.path.join(p, 'summary.json'), 'w'))"
                ),
            ],
            produces={"summary": (json_file(), "summary.json")},
        ),
        code(
            "write_verdict",
            argv=[
                "python3",
                "-c",
                (
                    "import json, os; "
                    "p = os.environ.get('PRODUCES_ROOT', '{produces_root}'); "
                    "os.makedirs(p, exist_ok=True); "
                    "step_dir = os.path.dirname(os.path.dirname(p)); "
                    "prev = os.path.join(os.path.dirname(step_dir), 'write_summary', 'v1', 'produces', 'summary.json'); "
                    "summary = json.load(open(prev)); "
                    "verdict = 'Text has ' + str(summary['word_count']) + ' words across ' + str(summary['line_count']) + ' lines.'; "
                    "json.dump({'verdict': verdict}, open(os.path.join(p, 'verdict.json'), 'w'))"
                ),
            ],
            produces={"verdict": (json_file(), "verdict.json")},
        ),
    ]
