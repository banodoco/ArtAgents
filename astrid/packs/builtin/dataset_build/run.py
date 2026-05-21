#!/usr/bin/env python3
"""Run the generic built-in training dataset builder."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .caption_providers import BudgetTracker, caption_candidate
from .config import (
    BudgetPreflightError,
    ConfigParseError,
    ParsedDatasetConfig,
    SecretPreflightError,
    load_dataset_config,
    preflight_budget_and_secrets,
)
from .filter_stages import BucketJudgeGate, DurationFilter
from .items import config_hash, deterministic_id, make_review_item, repo_relative_path, sha256_file, utc_now_iso
from .manifest import accepted_items, build_canonical_manifest, write_canonical_manifest
from .manifest_adapters import get_manifest_adapter
from .review import apply_review_decisions, write_human_review_final, write_review_data
from .source_providers import get_source_provider
from .state import make_initial_state, read_review_state, set_status, write_review_state


PACKAGE_ROOT = Path(__file__).resolve().parent
REVIEW_UI_ROOT = PACKAGE_ROOT / "review_ui"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Dataset build config JSON or YAML.")
    parser.add_argument("--out", type=Path, required=True, help="Run output directory.")
    parser.add_argument("--review-decisions", type=Path, help="Non-interactive review decisions JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preflight config, then print the planned run.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        parsed_config = load_dataset_config(args.config)
        preflight_budget_and_secrets(parsed_config)
    except (ConfigParseError, BudgetPreflightError, SecretPreflightError) as exc:
        print(f"builtin.dataset_build: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "orchestrator": "builtin.dataset_build",
                    "config": str(parsed_config.path),
                    "out": str(args.out),
                    "review_decisions": str(args.review_decisions) if args.review_decisions else None,
                    "schema_version_source": parsed_config.schema_version_source,
                    "warnings": list(parsed_config.warnings),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        summary = run_pipeline(parsed_config, args.out, review_decisions_path=args.review_decisions)
    except Exception as exc:  # noqa: BLE001 - CLI should record failed state and exit cleanly
        print(f"builtin.dataset_build: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def run_pipeline(
    parsed_config: ParsedDatasetConfig,
    out_dir: str | Path,
    *,
    review_decisions_path: str | Path | None = None,
    source_provider_kwargs: Mapping[str, Any] | None = None,
    caption_runner=None,
    human_review_runner=subprocess.run,
) -> dict[str, Any]:
    run_dir = Path(out_dir).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(parsed_config.data)
    config.setdefault("output", {})["run_dir"] = str(run_dir)
    _assert_under(run_dir, run_dir)

    dataset_id = str(config.get("dataset_id") or deterministic_id(parsed_config.path, config_hash(config), prefix="dataset"))
    state_path = run_dir / "review_state.json"
    state = make_initial_state(
        run_id=dataset_id,
        writer_id="builtin.dataset_build",
        config_hash=config_hash(config),
        buckets=config.get("buckets"),
        schema_version_source=parsed_config.schema_version_source,
        status="initializing",
    )
    write_review_state(state_path, state)

    try:
        set_status(state_path, "acquiring")
        candidates = _acquire_candidates(config, run_dir, source_provider_kwargs=source_provider_kwargs)
        review_items = [
            make_review_item(candidate, item_id=_item_id(candidate), bucket=_default_bucket(config))
            for candidate in candidates
        ]

        set_status(state_path, "filtering")
        active_items, rejected_items, filter_stats = _apply_filters(review_items, config)
        _update_state(state_path, {"filter_stats": filter_stats})

        set_status(state_path, "captioning")
        captioned = _caption_items(active_items, config, run_dir, caption_runner=caption_runner)
        all_items = [*captioned, *rejected_items]

        set_status(state_path, "reviewing")
        review_data_path = write_review_data(run_dir / "review_data.json", all_items)
        if review_decisions_path is not None:
            decisions = _load_review_decisions(review_decisions_path)
            _update_state(state_path, {"review_decisions": decisions, "submitted": True})
            write_human_review_final(run_dir, {"review_decisions": decisions, "submitted": True})
        elif (config.get("review") or {}).get("enabled", True):
            _run_human_review(run_dir, review_data_path, state_path, human_review_runner)
        else:
            decisions = _accept_all_decisions(captioned)
            _update_state(state_path, {"review_decisions": decisions, "submitted": True})
            write_human_review_final(run_dir, {"review_decisions": decisions, "submitted": True})

        reviewed_state = read_review_state(state_path)
        final_items = apply_review_decisions(all_items, reviewed_state)
        manifest_config = config.get("manifest") or {}
        adapter_id = str(manifest_config.get("adapter") or "ai-toolkit-ltx")
        canonical = build_canonical_manifest(
            final_items,
            dataset_id=dataset_id,
            source_provider=_source_provider_label(config),
            manifest_adapter=adapter_id,
            bucket_targets=config.get("buckets"),
        )
        canonical_path = write_canonical_manifest(run_dir / "final.manifest.json", canonical)
        adapter = get_manifest_adapter(
            adapter_id,
            out_path=run_dir / f"{adapter_id}.manifest.json",
            source_manifest=canonical_path,
        )
        adapter_path = adapter.export(accepted_items(canonical["items"]))
        set_status(state_path, "finalized")
        final_state = read_review_state(state_path)
        return {
            "run_dir": str(run_dir),
            "review_data": str(review_data_path),
            "review_state": str(state_path),
            "canonical_manifest": str(canonical_path),
            "adapter_manifest": str(adapter_path),
            "accepted": len(canonical["items"]),
            "state_status": final_state["status"],
            "state_version": final_state["state_version"],
        }
    except Exception as exc:
        if state_path.is_file():
            set_status(state_path, "failed", error={"type": type(exc).__name__, "message": str(exc)})
        raise


def _acquire_candidates(config: Mapping[str, Any], run_dir: Path, *, source_provider_kwargs: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, source in enumerate(config.get("sources", []) or []):
        provider_id = str(source["provider"])
        provider_config = dict(source.get("config") or {})
        provider_config.setdefault("dataset_config", config)
        provider_config.setdefault("out_dir", str(run_dir / "sources" / f"{index:02d}_{provider_id}"))
        provider = get_source_provider(provider_id, **dict(source_provider_kwargs or {}))
        for candidate in provider.acquire(provider_config):
            candidates.append(_confine_candidate_media(candidate, run_dir))
    return candidates


def _confine_candidate_media(candidate: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    item = dict(candidate)
    source_path = Path(str(item["media_path"])).expanduser()
    if not source_path.is_absolute():
        from astrid._paths import REPO_ROOT

        source_path = (REPO_ROOT / source_path).resolve()
    clips_dir = run_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    stem = _item_id(item)
    target = clips_dir / f"{stem}{source_path.suffix or '.mp4'}"
    if source_path.resolve() != target.resolve():
        shutil.copy2(source_path, target)
    item["media_path"] = repo_relative_path(target)
    item["content_hash"] = sha256_file(target)
    _assert_under(target, run_dir)
    return item


def _apply_filters(items: list[dict[str, Any]], config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    filter_stats: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = []
    duration_config = dict((config.get("filters") or {}).get("duration") or {})
    clip_config = config.get("clip_config") or {}
    duration_config.setdefault("min_s", clip_config.get("min_duration_s", 0.0))
    duration_config.setdefault("max_s", clip_config.get("max_duration_s", 60.0))
    active = items
    if duration_config.get("enabled", True):
        duration_result = DurationFilter().apply(active, {}, duration_config)
        active = duration_result.passed
        rejected.extend(duration_result.rejected)
        filter_stats[duration_result.stats["stage_id"]] = duration_result.stats

    bucket_config = dict(config)
    bucket_config["bucket_judge"] = dict((config.get("extensions") or {}).get("bucket_judge") or {})
    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping) and extensions.get("fixture_judge_dir") and "fixture_dir" not in bucket_config["bucket_judge"]:
        bucket_config["bucket_judge"]["fixture_dir"] = extensions["fixture_judge_dir"]
    if bucket_config["bucket_judge"].get("enabled", False):
        gate = BucketJudgeGate()
        bucket_result = gate.apply(active, {}, bucket_config)
        active = bucket_result.passed
        rejected.extend(bucket_result.rejected)
        filter_stats[bucket_result.stats["stage_id"]] = bucket_result.stats
    return active, rejected, filter_stats


def _caption_items(items: list[dict[str, Any]], config: Mapping[str, Any], run_dir: Path, *, caption_runner) -> list[dict[str, Any]]:
    caption_config = dict(config.get("caption") or {"provider": "visual_understand"})
    caption_config.setdefault("out_dir", str(run_dir / "captions"))
    caption_config.setdefault("budget_tracker", BudgetTracker.from_config(config))
    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping) and extensions.get("fixture_caption_dir") and "fixture_dir" not in caption_config:
        caption_config["fixture_dir"] = extensions["fixture_caption_dir"]
    if extensions.get("fixture_mode") is True:
        caption_config["fixture_mode"] = True
    captioned: list[dict[str, Any]] = []
    for item in items:
        if caption_runner is None:
            result, sidecar = caption_candidate(item, caption_config)
        else:
            result, sidecar = caption_candidate(item, caption_config, runner=caption_runner)
        updated = dict(item)
        updated["caption"] = {
            "text": result.text,
            "schema_version": result.schema_version,
            "confidence": result.confidence,
            "model": result.model,
        }
        if result.raw_response is not None:
            updated["caption"]["raw_response"] = result.raw_response
        updated["caption_file"] = repo_relative_path(sidecar)
        captioned.append(updated)
    return captioned


def _run_human_review(run_dir: Path, review_data_path: Path, state_path: Path, runner) -> None:
    out_path = run_dir / "review_server" / "human_review.final.json"
    cmd = [
        sys.executable,
        "-m",
        "astrid.packs.builtin.human_review.run",
        "--html",
        str(REVIEW_UI_ROOT),
        "--data",
        str(review_data_path),
        "--state",
        str(state_path),
        "--out",
        str(out_path),
        "--serve",
        f"/media={run_dir / 'clips'}",
        "--no-open",
    ]
    runner(cmd, check=True)


def _load_review_decisions(path: str | Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = payload.get("review_decisions", payload.get("decisions", payload.get("revisions", payload))) if isinstance(payload, Mapping) else payload
    decisions: dict[str, dict[str, Any]] = {}
    if isinstance(raw, Mapping):
        iterable = raw.items()
    elif isinstance(raw, list):
        iterable = ((entry.get("item_id"), entry) for entry in raw if isinstance(entry, Mapping))
    else:
        raise ValueError("review decisions JSON must be an object or list")
    for item_id, decision in iterable:
        if item_id is None or not isinstance(decision, Mapping):
            continue
        normalized = _normalize_decision(decision.get("decision", decision.get("review_status", "pending")))
        decisions[str(item_id)] = {
            "item_id": str(item_id),
            "decision": normalized,
            "reject_reason": decision.get("reject_reason"),
            "edited_caption": decision.get("edited_caption"),
            "reviewed_at": decision.get("reviewed_at") or utc_now_iso(),
            "state_version": int(decision.get("state_version", 0)),
        }
        if decision.get("reviewer_id"):
            decisions[str(item_id)]["reviewer_id"] = str(decision["reviewer_id"])
    return decisions


def _accept_all_decisions(items: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item["item_id"]): {
            "item_id": str(item["item_id"]),
            "decision": "accept",
            "reject_reason": None,
            "edited_caption": None,
            "reviewed_at": utc_now_iso(),
            "state_version": 0,
        }
        for item in items
    }


def _update_state(path: Path, updates: Mapping[str, Any]) -> dict[str, Any]:
    state = read_review_state(path)
    state.update(copy.deepcopy(dict(updates)))
    return write_review_state(path, state)


def _item_id(item: Mapping[str, Any]) -> str:
    if item.get("item_id"):
        return str(item["item_id"])
    return deterministic_id(item.get("source_type", ""), item.get("source_id", ""), item.get("scene_index", ""), prefix="item")


def _default_bucket(config: Mapping[str, Any]) -> str | None:
    buckets = config.get("buckets")
    if isinstance(buckets, Mapping) and len(buckets) == 1:
        return next(iter(buckets))
    return None


def _source_provider_label(config: Mapping[str, Any]) -> str | None:
    providers = [str(source.get("provider")) for source in config.get("sources", []) if isinstance(source, Mapping)]
    return providers[0] if len(set(providers)) == 1 and providers else ",".join(providers) if providers else None


def _normalize_decision(value: Any) -> str:
    if value in {"accepted", "accept", True}:
        return "accept"
    if value in {"rejected", "reject", False}:
        return "reject"
    return "pending"


def _assert_under(path: Path, root: Path) -> None:
    path.resolve().relative_to(root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
