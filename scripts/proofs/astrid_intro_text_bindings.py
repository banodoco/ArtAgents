"""Emit Stage1-native shot/text-binding specs for the canonical Astrid intro."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.proofs.astrid_intro_canonical_fixture import materialize_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--storyboard", type=Path, default=REPO_ROOT / "storyboards/astrid-intro.storyboard.json")
    parser.add_argument("--plan", type=Path, default=REPO_ROOT / "storyboards/astrid-intro.plan.json")
    parser.add_argument("--out", type=Path)
    return parser


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    fixture = materialize_fixture(
        storyboard_path=args.storyboard,
        plan_path=args.plan,
        source_repo=args.source_repo,
    )
    result = {
        "schema": "astrid.intro-text-bindings/v1",
        "sources": fixture["sources"],
        "counts": fixture["counts"],
        "shots": [
            {key: section[key] for key in ("index", "section_id", "shot_id", "name")}
            for section in fixture["sections"]
        ],
        "text_bindings": fixture["text_bindings"],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return result


if __name__ == "__main__":
    run()
