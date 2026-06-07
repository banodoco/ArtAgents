"""Canonical implementation for ``text_analysis.summarize``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from astrid.orchestrate import code, json_file, orchestrator
from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint, run_pack_main

guard_canonical_entrypoint("text_analysis.summarize")

PACK_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = PACK_ROOT / "fixtures" / "sample.txt"


@orchestrator("text_analysis.summarize")
def summarize():
    sample_path = repr(str(SAMPLE_PATH))
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
                    f"text = open({sample_path}).read(); "
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


def _write_summary_outputs(out_dir: Path) -> None:
    text = SAMPLE_PATH.read_text(encoding="utf-8")
    content = {
        "file": SAMPLE_PATH.name,
        "text": text,
        "char_count": len(text),
        "line_count": text.count("\n"),
    }
    words = text.split()
    summary = {
        "word_count": len(words),
        "char_count": content["char_count"],
        "line_count": content["line_count"],
        "preview": f"{text[:200]}..." if len(text) > 200 else text,
    }
    verdict = {
        "verdict": f"Text has {summary['word_count']} words across {summary['line_count']} lines."
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "content.json").write_text(json.dumps(content), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (out_dir / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read the bundled sample text fixture and emit summary JSON artifacts.",
    )
    parser.add_argument("--out", required=True, help="Output directory for JSON artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    def _runner() -> int:
        args = _build_parser().parse_args(argv)
        _write_summary_outputs(Path(args.out).expanduser().resolve())
        return 0

    return run_pack_main(
        "text_analysis.summarize",
        _runner,
        argv=argv,
        recovery_command="python3 -m astrid orchestrators run text_analysis.summarize --help",
    )


if __name__ == "__main__":
    raise SystemExit(main())
