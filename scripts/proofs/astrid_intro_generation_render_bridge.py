"""Emit the canonical 26-section source-to-runtime materialization boundary.

The output is deterministic preparation evidence, not a render receipt.  It
contains no runtime locator or credentials and performs no workspace writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.proofs.astrid_intro_canonical_fixture import materialize_fixture
from scripts import build_storyboard

REPO_ROOT = Path(__file__).resolve().parents[2]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _timeline_summary(*, storyboard: Path, plan: Path, source_repo: Path) -> dict:
    story = json.loads(storyboard.read_text(encoding="utf-8"))
    plan_value = json.loads(plan.read_text(encoding="utf-8"))

    def import_asset(path: Path) -> build_storyboard.AssetImport:
        resolved = path.resolve(strict=True)
        resolved.relative_to(source_repo.resolve(strict=True))
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        return build_storyboard.AssetImport(
            file=f"sha256/{digest}",
            content_sha256=digest,
            media_id=f"fixture-{digest[:24]}",
        )

    config, registry, report = build_storyboard.compile_storyboard(
        story,
        base_dir=source_repo / "storyboards",
        plan=plan_value,
        import_asset=import_asset,
    )
    track_counts = {
        track["id"]: sum(clip["track"] == track["id"] for clip in config["clips"])
        for track in config["tracks"]
    }
    return {
        "clips": len(config["clips"]),
        "assets": len(registry["assets"]),
        "tracks": track_counts,
        "duration": report["total_duration"],
        "config_sha256": _canonical_hash(config),
        "registry_sha256": _canonical_hash(registry),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--storyboard", type=Path, default=REPO_ROOT / "storyboards/astrid-intro.storyboard.json")
    parser.add_argument("--plan", type=Path, default=REPO_ROOT / "storyboards/astrid-intro.plan.json")
    parser.add_argument("--out", type=Path)
    return parser


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    result = materialize_fixture(
        storyboard_path=args.storyboard,
        plan_path=args.plan,
        source_repo=args.source_repo,
    )
    result["timeline"] = _timeline_summary(
        storyboard=args.storyboard,
        plan=args.plan,
        source_repo=args.source_repo,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return result


if __name__ == "__main__":
    run()
