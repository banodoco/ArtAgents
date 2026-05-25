#!/usr/bin/env python3
"""Run the generic built-in training dataset builder."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import write_json_atomic

from .acquisition import build_acquisition_request
from .budget import BudgetTracker
from .caption_validation import validate_accepted_captions
from .caption_providers import caption_candidate
from .config import (
    BudgetPreflightError,
    ConfigParseError,
    ParsedDatasetConfig,
    SecretPreflightError,
    load_dataset_config,
    normalize_filter_stages,
    preflight_budget_and_secrets,
)
from .filter_stages import canonical_source_id, get_filter_stage
from .items import config_hash, deterministic_id, make_review_item, repo_relative_path, sha256_file, utc_now_iso
from .manifest import accepted_items, build_canonical_manifest, write_canonical_manifest
from .manifest_adapters import get_manifest_adapter
from .review import apply_review_decisions, write_human_review_final, write_review_data
from .reports.quality_report import write_quality_report
from .source_providers import get_source_provider
from .state import make_initial_state, read_review_state, set_status, write_review_state


PACKAGE_ROOT = Path(__file__).resolve().parent
REVIEW_UI_ROOT = PACKAGE_ROOT / "review_ui"


class ResumeConfigMismatchError(ValueError):
    """Raised when an existing run state belongs to a different config."""


@dataclass
class DatasetRunServices:
    """Run-scoped services shared across dataset-build phases."""

    budget_tracker: BudgetTracker
    filter_stage_factory: Callable[..., Any] = get_filter_stage
    filter_stage_runners: Mapping[str, Any] = field(default_factory=dict)
    caption_runner: Any | None = None
    human_review_runner: Any = subprocess.run
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    artifact_helpers: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        *,
        caption_runner: Any | None = None,
        human_review_runner: Any = subprocess.run,
        filter_stage_factory: Callable[..., Any] = get_filter_stage,
        filter_stage_runners: Mapping[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        artifact_helpers: Mapping[str, Any] | None = None,
    ) -> "DatasetRunServices":
        return cls(
            budget_tracker=BudgetTracker.from_config(config, clock=clock, sleep=sleep),
            filter_stage_factory=filter_stage_factory,
            filter_stage_runners=dict(filter_stage_runners or {}),
            caption_runner=caption_runner,
            human_review_runner=human_review_runner,
            clock=clock,
            sleep=sleep,
            artifact_helpers=dict(artifact_helpers or {}),
        )


@dataclass
class RoundExecutionResult:
    """Artifacts and item state produced by one dataset-build round."""

    round_index: int
    all_items: list[dict[str, Any]]
    captioned: list[dict[str, Any]]
    review_data_path: Path
    filter_stats: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Dataset build config JSON or YAML.")
    parser.add_argument("--out", type=Path, required=True, help="Run output directory.")
    parser.add_argument("--review-decisions", type=Path, help="Non-interactive review decisions JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and preflight config, then print the planned run.")
    review_modes = parser.add_mutually_exclusive_group()
    review_modes.add_argument("--skip-review", action="store_true", help="Do not launch human review or auto-accept; finalize with existing decisions only.")
    review_modes.add_argument("--review-only", action="store_true", help="Resume from existing review_data.json and run only review/finalization.")
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
                    "quality_report": str(Path(args.out).expanduser().resolve() / "quality_report.json"),
                    "review_decisions": str(args.review_decisions) if args.review_decisions else None,
                    "schema_version_source": parsed_config.schema_version_source,
                    "warnings": list(parsed_config.warnings),
                    "filter_stages": _dry_run_filter_stages(parsed_config.data),
                    "budget_limits": _budget_limits(parsed_config.data),
                    "fixture_mode": _fixture_mode(parsed_config.data),
                    "skip_review": bool(args.skip_review),
                    "review_only": bool(args.review_only),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        summary = run_pipeline(
            parsed_config,
            args.out,
            review_decisions_path=args.review_decisions,
            skip_review=args.skip_review,
            review_only=args.review_only,
        )
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
    filter_stage_factory: Callable[..., Any] = get_filter_stage,
    filter_stage_runners: Mapping[str, Any] | None = None,
    human_review_runner=subprocess.run,
    services: DatasetRunServices | None = None,
    skip_review: bool = False,
    review_only: bool = False,
) -> dict[str, Any]:
    run_dir = Path(out_dir).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(parsed_config.data)
    config.setdefault("output", {})["run_dir"] = str(run_dir)
    _assert_under(run_dir, run_dir)
    services = services or DatasetRunServices.from_config(
        config,
        caption_runner=caption_runner,
        filter_stage_factory=filter_stage_factory,
        filter_stage_runners=filter_stage_runners,
        human_review_runner=human_review_runner,
    )

    dataset_id = str(config.get("dataset_id") or deterministic_id(parsed_config.path, config_hash(config), prefix="dataset"))
    manifest_config = config.get("manifest") if isinstance(config.get("manifest"), Mapping) else {}
    adapter_id = str(manifest_config.get("adapter") or "ai-toolkit-ltx")
    paths = _checkpoint_paths(run_dir, adapter_id=adapter_id)
    state_path = paths["review_state"]
    state = _load_or_create_review_state(state_path, dataset_id=dataset_id, config=config, parsed_config=parsed_config)
    resume_status = "reviewing" if review_only else str(state.get("status") or "initializing")
    if resume_status == "finalized":
        return _finalized_summary(run_dir, paths, state_path)
    if review_only and not paths["review_data"].is_file():
        raise FileNotFoundError(f"--review-only requires existing {paths['review_data']}")

    try:
        stages = _enabled_filter_stages(config)
        round_result = _execute_round(
            round_index=0,
            config=config,
            run_dir=run_dir,
            paths=paths,
            state_path=state_path,
            resume_status=resume_status,
            stages=stages,
            services=services,
            source_provider_kwargs=source_provider_kwargs,
            review_decisions_path=review_decisions_path,
            skip_review=skip_review,
        )
        all_items = round_result.all_items
        review_data_path = round_result.review_data_path
        all_items, review_data_path = _run_top_up_rounds(
            config=config,
            run_dir=run_dir,
            paths=paths,
            state_path=state_path,
            stages=stages,
            services=services,
            source_provider_kwargs=source_provider_kwargs,
            review_decisions_path=review_decisions_path,
            skip_review=skip_review,
            initial_items=all_items,
            initial_review_data_path=review_data_path,
        )

        if skip_review and review_decisions_path is None:
            reviewed_items = _reviewed_items(all_items, state_path, persist_caption_sidecars=False)
            _maybe_write_quality_report(
                paths,
                config,
                state_path,
                services,
                items=reviewed_items,
                final_shortfalls=_bucket_shortfalls(reviewed_items, config),
            )
            final_state = read_review_state(state_path)
            return {
                "run_dir": str(run_dir),
                "work_preview": str(paths["work_preview"]),
                "review_data": str(review_data_path),
                "review_state": str(state_path),
                "canonical_manifest": None,
                "adapter_manifest": None,
                "quality_report": str(paths["quality_report"]),
                "accepted": 0,
                "state_status": final_state["status"],
                "state_version": final_state["state_version"],
            }

        remaining_shortfalls = _bucket_shortfalls(_reviewed_items(all_items, state_path, persist_caption_sidecars=False), config)
        if remaining_shortfalls:
            set_status(
                state_path,
                "failed",
                error={
                    "stage": "top_up",
                    "message": f"required bucket targets unmet after top-up rounds: {remaining_shortfalls}",
                    "timestamp": utc_now_iso(),
                },
            )
            reviewed_items = _reviewed_items(all_items, state_path, persist_caption_sidecars=False)
            _maybe_write_quality_report(paths, config, state_path, services, items=reviewed_items, final_shortfalls=remaining_shortfalls)
            final_state = read_review_state(state_path)
            return {
                "run_dir": str(run_dir),
                "work_preview": str(paths["work_preview"]),
                "review_data": str(review_data_path),
                "review_state": str(state_path),
                "canonical_manifest": None,
                "adapter_manifest": None,
                "quality_report": str(paths["quality_report"]),
                "accepted": len([item for item in _reviewed_items(all_items, state_path, persist_caption_sidecars=False) if item.get("review_status") == "accepted"]),
                "state_status": final_state["status"],
                "state_version": final_state["state_version"],
                "bucket_shortfalls": remaining_shortfalls,
            }

        reviewed_state = read_review_state(state_path)
        final_items = apply_review_decisions(all_items, reviewed_state)
        caption_validation = validate_accepted_captions(final_items, config)
        if caption_validation.failures:
            _phase_prepare_review_data(paths, caption_validation.items, config)
            write_review_state(
                state_path,
                {
                    **read_review_state(state_path),
                    "caption_validation_failures": caption_validation.failures,
                },
            )
            set_status(
                state_path,
                "failed",
                error={
                    "stage": "caption_validation",
                    "message": f"accepted captions failed validation: {caption_validation.failures}",
                    "timestamp": utc_now_iso(),
                },
            )
            _maybe_write_quality_report(
                paths,
                config,
                state_path,
                services,
                items=caption_validation.items,
                final_shortfalls={},
            )
            final_state = read_review_state(state_path)
            return {
                "run_dir": str(run_dir),
                "work_preview": str(paths["work_preview"]),
                "review_data": str(paths["review_data"]),
                "review_state": str(state_path),
                "canonical_manifest": None,
                "adapter_manifest": None,
                "quality_report": str(paths["quality_report"]),
                "accepted": len([item for item in caption_validation.items if item.get("review_status") == "accepted"]),
                "state_status": final_state["status"],
                "state_version": final_state["state_version"],
                "caption_validation_failures": caption_validation.failures,
            }

        canonical_path, adapter_path, canonical = _phase_finalize_manifests(
            run_dir,
            state_path,
            caption_validation.items,
            config,
            paths=paths,
            dataset_id=dataset_id,
            items_are_reviewed=True,
        )
        set_status(state_path, "finalized")
        _maybe_write_quality_report(
            paths,
            config,
            state_path,
            services,
            items=caption_validation.items,
            final_shortfalls={},
            canonical_manifest=canonical,
        )
        _mirror_round_checkpoints(paths, _round_checkpoint_paths(run_dir, 0), "review_state")
        final_state = read_review_state(state_path)
        return {
            "run_dir": str(run_dir),
            "work_preview": str(paths["work_preview"]),
            "review_data": str(review_data_path),
            "review_state": str(state_path),
            "canonical_manifest": str(canonical_path),
            "adapter_manifest": str(adapter_path),
            "quality_report": str(paths["quality_report"]),
            "accepted": len(canonical["items"]),
            "state_status": final_state["status"],
            "state_version": final_state["state_version"],
        }
    except Exception as exc:
        if state_path.is_file():
            set_status(state_path, "failed", error={"type": type(exc).__name__, "message": str(exc)})
            _maybe_write_quality_report(
                paths,
                config,
                state_path,
                services,
                items=_best_effort_report_items(paths),
                final_shortfalls=None,
            )
        raise


def _maybe_write_quality_report(
    paths: Mapping[str, Path],
    config: Mapping[str, Any],
    state_path: Path,
    services: DatasetRunServices,
    *,
    items: list[Mapping[str, Any]],
    final_shortfalls: Mapping[str, int] | None,
    canonical_manifest: Mapping[str, Any] | None = None,
) -> Path | None:
    try:
        state = read_review_state(state_path)
        report_path = write_quality_report(
            paths["quality_report"],
            items=items,
            config=config,
            state=state,
            budget=services.budget_tracker.as_dict(),
            final_shortfalls=final_shortfalls,
            canonical_manifest=canonical_manifest,
        )
        updated = read_review_state(state_path)
        updated["quality_report"] = str(report_path)
        write_review_state(state_path, updated)
        return report_path
    except Exception:
        return None


def _best_effort_report_items(paths: Mapping[str, Path]) -> list[dict[str, Any]]:
    if paths["review_data"].is_file():
        return _load_review_data(paths["review_data"])
    if paths["filtered_items"].is_file():
        active, rejected = _load_filtered_items(paths["filtered_items"])
        return [*active, *rejected]
    if paths["candidates"].is_file():
        return _load_candidates(paths["candidates"])
    return []


def _execute_round(
    *,
    round_index: int,
    config: Mapping[str, Any],
    run_dir: Path,
    paths: Mapping[str, Path],
    state_path: Path,
    resume_status: str,
    stages: list[Mapping[str, Any]],
    services: DatasetRunServices,
    source_provider_kwargs: Mapping[str, Any] | None,
    review_decisions_path: str | Path | None,
    skip_review: bool,
    acquisition_request: Mapping[str, Any] | None = None,
) -> RoundExecutionResult:
    round_paths = _round_checkpoint_paths(run_dir, round_index)
    review_data_path = paths["review_data"]

    if resume_status == "reviewing" and paths["review_data"].is_file():
        all_items = _load_review_data(paths["review_data"])
        captioned = [item for item in all_items if item.get("review_status") != "rejected"]
        filter_stats = dict(read_review_state(state_path).get("filter_stats") or {})
        _mirror_round_checkpoints(paths, round_paths, "review_data", "filtered_items", "work_preview", "candidates")
    else:
        if resume_status in {"preview_ready", "captioning"} and paths["filtered_items"].is_file():
            active_items, rejected_items = _load_filtered_items(paths["filtered_items"])
            filter_stats = dict(read_review_state(state_path).get("filter_stats") or {})
            _mirror_round_checkpoints(paths, round_paths, "filtered_items", "work_preview", "candidates")
        else:
            candidates = _load_candidates(paths["candidates"]) if paths["candidates"].is_file() else None
            if candidates is None:
                set_status(state_path, "acquiring")
                _mirror_round_checkpoints(paths, round_paths, "review_state")
                candidates = _phase_acquire_candidates(
                    config,
                    run_dir,
                    paths=paths,
                    state_path=state_path,
                    source_provider_kwargs=source_provider_kwargs,
                    acquisition_request=acquisition_request,
                )
            else:
                _record_processed_sources(state_path, candidates)
            _mirror_round_checkpoints(paths, round_paths, "candidates", "review_state")
            review_items = _phase_prepare_review_items(candidates, config)

            set_status(state_path, "filtering")
            active_items, rejected_items, filter_stats = _phase_deterministic_filters(review_items, config, paths, stages, services)
            _write_filtered_items(paths["filtered_items"], active_items, rejected_items, phase="post_deterministic_filters")
            _update_state(state_path, {"filter_stats": filter_stats})
            _mirror_round_checkpoints(paths, round_paths, "work_preview", "filtered_items", "review_state")
            set_status(state_path, "preview_ready")
            _mirror_round_checkpoints(paths, round_paths, "review_state")

        if resume_status != "captioning":
            active_items, expensive_rejected, expensive_stats = _phase_model_backed_filters(active_items, config, stages, services)
            rejected_items.extend(expensive_rejected)
            filter_stats.update(expensive_stats)
            _write_filtered_items(paths["filtered_items"], active_items, rejected_items, phase="post_model_backed_filters")
            _update_state(state_path, {"filter_stats": filter_stats})
            _mirror_round_checkpoints(paths, round_paths, "filtered_items", "review_state")

        set_status(state_path, "captioning")
        _mirror_round_checkpoints(paths, round_paths, "review_state")
        captioned = _phase_caption_items(active_items, config, run_dir, services)
        all_items = [*captioned, *rejected_items]

        set_status(state_path, "reviewing")
        review_data_path = _phase_prepare_review_data(paths, all_items, config)
        _mirror_round_checkpoints(paths, round_paths, "review_data", "review_state")

    _phase_human_review(
        run_dir,
        state_path,
        review_data_path,
        captioned,
        config,
        review_decisions_path=review_decisions_path,
        services=services,
        skip_review=skip_review,
        round_index=round_index,
        review_output_dir=run_dir if round_index == 0 else run_dir / "rounds" / str(round_index),
        required_decision_item_ids={str(item["item_id"]) for item in captioned if item.get("review_status") != "rejected"},
    )
    _mirror_round_checkpoints(paths, round_paths, "review_state", "review_data", "human_review_final")
    return RoundExecutionResult(
        round_index=round_index,
        all_items=all_items,
        captioned=captioned,
        review_data_path=review_data_path,
        filter_stats=filter_stats,
    )


def _run_top_up_rounds(
    *,
    config: Mapping[str, Any],
    run_dir: Path,
    paths: Mapping[str, Path],
    state_path: Path,
    stages: list[Mapping[str, Any]],
    services: DatasetRunServices,
    source_provider_kwargs: Mapping[str, Any] | None,
    review_decisions_path: str | Path | None,
    skip_review: bool,
    initial_items: list[dict[str, Any]],
    initial_review_data_path: Path,
) -> tuple[list[dict[str, Any]], Path]:
    all_items = [copy.deepcopy(item) for item in initial_items]
    review_data_path = initial_review_data_path
    max_rounds = _max_top_up_rounds(config)
    initial_reviewed = _reviewed_items(all_items, state_path, persist_caption_sidecars=False)
    if not _bucket_shortfalls(initial_reviewed, config):
        return all_items, review_data_path
    if max_rounds <= 0:
        return all_items, review_data_path

    for round_index in range(1, max_rounds + 1):
        reviewed_items = _reviewed_items(all_items, state_path, persist_caption_sidecars=False)
        shortfalls = _bucket_shortfalls(reviewed_items, config)
        _update_bucket_progress(state_path, reviewed_items, config, top_up_rounds=round_index - 1)
        if not shortfalls:
            return all_items, review_data_path
        if skip_review and review_decisions_path is None:
            return all_items, review_data_path

        request = _top_up_acquisition_request(round_index, shortfalls, reviewed_items, state_path)
        top_up_config = _config_for_top_up(config, request)
        round_paths = _round_checkpoint_paths(run_dir, round_index)
        _update_state(state_path, {"submitted": False})
        result = _execute_round(
            round_index=round_index,
            config=top_up_config,
            run_dir=run_dir,
            paths=round_paths,
            state_path=state_path,
            resume_status="initializing",
            stages=stages,
            services=services,
            source_provider_kwargs=source_provider_kwargs,
            review_decisions_path=review_decisions_path,
            skip_review=skip_review,
            acquisition_request=request,
        )
        _update_bucket_progress(state_path, _reviewed_items([*all_items, *result.all_items], state_path, persist_caption_sidecars=False), config, top_up_rounds=round_index)
        all_items.extend(result.all_items)
        review_data_path = result.review_data_path

    return all_items, review_data_path


def _reviewed_items(items: list[dict[str, Any]], state_path: Path, *, persist_caption_sidecars: bool) -> list[dict[str, Any]]:
    return apply_review_decisions(items, read_review_state(state_path), persist_caption_sidecars=persist_caption_sidecars)


def _max_top_up_rounds(config: Mapping[str, Any]) -> int:
    review = config.get("review") if isinstance(config.get("review"), Mapping) else {}
    top_up = review.get("top_up") if isinstance(review.get("top_up"), Mapping) else {}
    try:
        return max(0, int(top_up.get("max_rounds", 0)))
    except (TypeError, ValueError):
        return 0


def _bucket_shortfalls(items: list[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, int]:
    targets = config.get("buckets") if isinstance(config.get("buckets"), Mapping) else {}
    accepted_by_bucket: dict[str, int] = {}
    for item in items:
        if item.get("review_status") != "accepted":
            continue
        bucket = str(item.get("bucket") or "unbucketed")
        accepted_by_bucket[bucket] = accepted_by_bucket.get(bucket, 0) + 1
    shortfalls: dict[str, int] = {}
    for bucket, target in targets.items():
        target_count = _bucket_target_count(target)
        if target_count <= 0:
            continue
        shortfall = target_count - accepted_by_bucket.get(str(bucket), 0)
        if shortfall > 0:
            shortfalls[str(bucket)] = shortfall
    return shortfalls


def _bucket_target_count(target: Any) -> int:
    try:
        if isinstance(target, Mapping):
            return max(0, int(target.get("target_count", 0)))
        return max(0, int(target))
    except (TypeError, ValueError):
        return 0


def _update_bucket_progress(
    state_path: Path,
    items: list[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    top_up_rounds: int,
) -> dict[str, Any]:
    state = read_review_state(state_path)
    buckets = _bucket_progress(items, config)
    if buckets:
        state["buckets"] = buckets
    state["top_up_rounds"] = top_up_rounds
    return write_review_state(state_path, state)


def _bucket_progress(items: list[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    targets = config.get("buckets") if isinstance(config.get("buckets"), Mapping) else {}
    buckets: dict[str, dict[str, Any]] = {}
    for bucket, target in targets.items():
        buckets[str(bucket)] = {"target_count": _bucket_target_count(target), "accepted": 0, "rejected": 0, "pending": 0, "item_ids": []}
    for item in items:
        bucket = str(item.get("bucket") or "unbucketed")
        entry = buckets.setdefault(bucket, {"target_count": 0, "accepted": 0, "rejected": 0, "pending": 0, "item_ids": []})
        status = str(item.get("review_status") or "pending")
        if status == "accepted":
            entry["accepted"] += 1
        elif status == "rejected":
            entry["rejected"] += 1
        else:
            entry["pending"] += 1
        item_id = item.get("item_id")
        if item_id is not None:
            entry["item_ids"].append(str(item_id))
    return buckets


def _top_up_acquisition_request(
    round_index: int,
    shortfalls: Mapping[str, int],
    items: list[Mapping[str, Any]],
    state_path: Path,
) -> dict[str, Any]:
    state = read_review_state(state_path)
    return build_acquisition_request(
        processed_source_ids=state.get("processed_source_ids") or [],
        acquisition_request={
            "round_index": round_index,
            "target_shortfalls": dict(shortfalls),
            "exclude_candidate_ids": _item_ids(items),
            "exclude_source_ids": _source_ids(items),
            "exclude_media_hashes": _content_hashes(items),
            "feedback_hints": _feedback_hints_from_rejections(items),
        },
    )


def _config_for_top_up(config: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(dict(config))
    feedback_hints = list(request.get("feedback_hints") or [])
    filters = updated.get("filters")
    stages = filters.get("stages") if isinstance(filters, Mapping) else None
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict) or stage.get("stage_id") not in {"semantic_visual_filter", "semantic_video_filter"}:
                continue
            stage_config = stage.setdefault("config", {})
            if isinstance(stage_config, dict):
                stage_config["top_up_feedback_hints"] = feedback_hints
    return updated


def _item_ids(items: list[Mapping[str, Any]]) -> list[str]:
    return sorted({str(item.get("item_id")) for item in items if item.get("item_id")})


def _source_ids(items: list[Mapping[str, Any]]) -> list[str]:
    source_ids = {str(item.get("source_id")) for item in items if item.get("source_id")}
    for item in items:
        source_id = canonical_source_id(item)
        if source_id:
            source_ids.add(source_id)
    return sorted(source_ids)


def _content_hashes(items: list[Mapping[str, Any]]) -> list[str]:
    return sorted({str(item.get("content_hash")) for item in items if item.get("content_hash")})


def _feedback_hints_from_rejections(items: list[Mapping[str, Any]]) -> list[str]:
    hints: set[str] = set()
    for item in items:
        if item.get("review_status") != "rejected":
            continue
        filter_results = item.get("filter_results")
        if not isinstance(filter_results, Mapping):
            continue
        for result in filter_results.values():
            if not isinstance(result, Mapping):
                continue
            hint = result.get("feedback_hint")
            if isinstance(hint, str) and hint:
                hints.add(hint)
            reason = result.get("reason")
            if isinstance(reason, str) and reason:
                hints.add(reason)
    return sorted(hints)


def _phase_acquire_candidates(
    config: Mapping[str, Any],
    run_dir: Path,
    *,
    paths: Mapping[str, Path],
    state_path: Path,
    source_provider_kwargs: Mapping[str, Any] | None,
    acquisition_request: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates = _acquire_candidates(config, run_dir, source_provider_kwargs=source_provider_kwargs, acquisition_request=acquisition_request)
    _write_json(paths["candidates"], {"candidates": candidates})
    _record_processed_sources(state_path, candidates)
    if isinstance(config, Mapping):
        acquisition_results = config.get("_acquisition_results")
        if isinstance(acquisition_results, list) and acquisition_results:
            _record_acquisition_results(state_path, acquisition_results)
    return candidates


def _phase_prepare_review_items(candidates: list[dict[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        make_review_item(candidate, item_id=_item_id(candidate), bucket=_default_bucket(config))
        for candidate in candidates
    ]


def _phase_deterministic_filters(
    review_items: list[dict[str, Any]],
    config: Mapping[str, Any],
    paths: Mapping[str, Path],
    stages: list[Mapping[str, Any]],
    services: DatasetRunServices,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    active_items, rejected_items, filter_stats = _apply_filter_stages(review_items, stages, model_backed=False, services=services)
    _write_work_preview(paths["work_preview"], config, active_items, rejected_items, filter_stats, stages)
    return active_items, rejected_items, filter_stats


def _phase_model_backed_filters(
    active_items: list[dict[str, Any]],
    config: Mapping[str, Any],
    stages: list[Mapping[str, Any]],
    services: DatasetRunServices,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return _apply_filter_stages(active_items, stages, model_backed=True, services=services)


def _phase_caption_items(items: list[dict[str, Any]], config: Mapping[str, Any], run_dir: Path, services: DatasetRunServices) -> list[dict[str, Any]]:
    return _caption_items(items, config, run_dir, services)


def _phase_prepare_review_data(paths: Mapping[str, Path], all_items: list[dict[str, Any]], config: Mapping[str, Any]) -> Path:
    return write_review_data(paths["review_data"], _apply_review_sampling(all_items, config))


def _apply_review_sampling(items: list[dict[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    review_config = config.get("review") if isinstance(config.get("review"), Mapping) else {}
    sampling_config = review_config.get("sampling") if isinstance(review_config, Mapping) else None
    if not isinstance(sampling_config, Mapping):
        return [copy.deepcopy(item) for item in items]

    mode = str(sampling_config.get("mode") or "all")
    sample_count = _sampling_count(sampling_config, default=len(items))
    ordered_item_ids = [str(item.get("item_id") or _item_id(item)) for item in items]
    if mode == "top_n":
        sampled_item_ids = set(ordered_item_ids[:sample_count])
    elif mode == "random_sample":
        ranked = sorted(
            ordered_item_ids,
            key=lambda item_id: deterministic_id("review_sampling", item_id, prefix="sample"),
        )
        sampled_item_ids = set(ranked[:sample_count])
    else:
        mode = "all"
        sampled_item_ids = set(ordered_item_ids)
        sample_count = len(ordered_item_ids)

    sampled_rank = {
        item_id: rank
        for rank, item_id in enumerate(
            [item_id for item_id in ordered_item_ids if item_id in sampled_item_ids],
            start=1,
        )
    }
    marked: list[dict[str, Any]] = []
    for item in items:
        updated = copy.deepcopy(item)
        item_id = str(updated.get("item_id") or _item_id(updated))
        marker: dict[str, Any] = {
            "sampled": item_id in sampled_item_ids,
            "mode": mode,
            "sample_count": sample_count,
        }
        if item_id in sampled_rank:
            marker["rank"] = sampled_rank[item_id]
        updated["review_sampled"] = marker
        marked.append(updated)
    return marked


def _sampling_count(sampling_config: Mapping[str, Any], *, default: int) -> int:
    raw = sampling_config.get("sample_count", default)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def _phase_human_review(
    run_dir: Path,
    state_path: Path,
    review_data_path: Path,
    captioned: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    review_decisions_path: str | Path | None,
    services: DatasetRunServices,
    skip_review: bool,
    round_index: int = 0,
    review_output_dir: Path | None = None,
    required_decision_item_ids: set[str] | None = None,
) -> None:
    output_dir = review_output_dir or run_dir
    if review_decisions_path is not None:
        decisions = _load_review_decisions(review_decisions_path, round_index=round_index)
        _require_review_decisions(decisions, required_decision_item_ids or set(), round_index=round_index)
        _merge_review_decisions(state_path, decisions, submitted=True)
        write_human_review_final(output_dir, {"review_decisions": decisions, "submitted": True, "round_index": round_index})
    elif skip_review:
        return
    elif (config.get("review") or {}).get("enabled", True):
        _run_human_review(output_dir, review_data_path, state_path, services.human_review_runner, media_root=run_dir / "clips")
    else:
        decisions = _accept_all_decisions(captioned)
        _merge_review_decisions(state_path, decisions, submitted=True)
        write_human_review_final(output_dir, {"review_decisions": decisions, "submitted": True, "round_index": round_index})


def _phase_finalize_manifests(
    run_dir: Path,
    state_path: Path,
    all_items: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    paths: Mapping[str, Path],
    dataset_id: str,
    items_are_reviewed: bool = False,
) -> tuple[Path, Path, dict[str, Any]]:
    if items_are_reviewed:
        final_items = [copy.deepcopy(item) for item in all_items]
    else:
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
    canonical_path = write_canonical_manifest(paths["canonical_manifest"], canonical)
    adapter = get_manifest_adapter(
        adapter_id,
        out_path=paths["adapter_manifest"],
        source_manifest=canonical_path,
    )
    adapter_path = adapter.export(accepted_items(canonical["items"]))
    return canonical_path, adapter_path, canonical


def _finalized_summary(run_dir: Path, paths: Mapping[str, Path], state_path: Path) -> dict[str, Any]:
    final_state = read_review_state(state_path)
    canonical = _read_json(paths["canonical_manifest"]) if paths["canonical_manifest"].is_file() else {"items": []}
    return {
        "run_dir": str(run_dir),
        "work_preview": str(paths["work_preview"]),
        "review_data": str(paths["review_data"]),
        "review_state": str(state_path),
        "canonical_manifest": str(paths["canonical_manifest"]),
        "adapter_manifest": str(paths["adapter_manifest"]),
        "quality_report": str(paths["quality_report"]),
        "accepted": len(canonical.get("items") or []) if isinstance(canonical, Mapping) else 0,
        "state_status": final_state["status"],
        "state_version": final_state["state_version"],
    }


def _checkpoint_paths(run_dir: Path, *, adapter_id: str = "ai-toolkit-ltx") -> dict[str, Path]:
    return {
        "review_state": run_dir / "review_state.json",
        "candidates": run_dir / "candidates.json",
        "work_preview": run_dir / "work_preview.json",
        "filtered_items": run_dir / "filtered_items.json",
        "review_data": run_dir / "review_data.json",
        "canonical_manifest": run_dir / "final.manifest.json",
        "adapter_manifest": run_dir / f"{adapter_id}.manifest.json",
        "quality_report": run_dir / "quality_report.json",
        "human_review_final": run_dir / "review_server" / "human_review.final.json",
    }


def _round_checkpoint_paths(run_dir: Path, round_index: int) -> dict[str, Path]:
    round_dir = run_dir / "rounds" / str(round_index)
    return {
        "review_state": round_dir / "review_state.json",
        "candidates": round_dir / "candidates.json",
        "work_preview": round_dir / "work_preview.json",
        "filtered_items": round_dir / "filtered_items.json",
        "review_data": round_dir / "review_data.json",
        "human_review_final": round_dir / "review_server" / "human_review.final.json",
    }


def _mirror_round_checkpoints(source_paths: Mapping[str, Path], round_paths: Mapping[str, Path], *keys: str) -> None:
    for key in keys:
        source = source_paths.get(key)
        target = round_paths.get(key)
        if source is None or target is None or not source.is_file():
            continue
        if source.resolve() == target.resolve():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _load_or_create_review_state(
    state_path: Path,
    *,
    dataset_id: str,
    config: Mapping[str, Any],
    parsed_config: ParsedDatasetConfig,
) -> dict[str, Any]:
    expected_hash = config_hash(config)
    if state_path.is_file():
        state = read_review_state(state_path)
        actual_hash = state.get("config_hash")
        if actual_hash != expected_hash:
            raise ResumeConfigMismatchError(
                f"existing review_state.json config_hash {actual_hash!r} does not match current config_hash {expected_hash!r}"
            )
        return state
    state = make_initial_state(
        run_id=dataset_id,
        writer_id="builtin.dataset_build",
        config_hash=expected_hash,
        buckets=config.get("buckets"),
        schema_version_source=parsed_config.schema_version_source,
        status="initializing",
    )
    return write_review_state(state_path, state)


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    candidates = payload.get("candidates") if isinstance(payload, Mapping) else payload
    if not isinstance(candidates, list):
        raise ValueError(f"{path.name} must contain a candidates list")
    return [dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)]


def _write_filtered_items(path: Path, active: list[dict[str, Any]], rejected: list[dict[str, Any]], *, phase: str) -> Path:
    return _write_json(path, {"phase": phase, "active": active, "rejected": rejected})


def _load_filtered_items(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path.name} must contain filtered item groups")
    active = payload.get("active")
    rejected = payload.get("rejected")
    if not isinstance(active, list) or not isinstance(rejected, list):
        raise ValueError(f"{path.name} must contain active and rejected lists")
    return [dict(item) for item in active if isinstance(item, Mapping)], [dict(item) for item in rejected if isinstance(item, Mapping)]


def _load_review_data(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    items = payload.get("items") if isinstance(payload, Mapping) else payload
    if not isinstance(items, list):
        raise ValueError(f"{path.name} must contain an items list")
    return [dict(item) for item in items if isinstance(item, Mapping)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_processed_sources(state_path: Path, candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    state = read_review_state(state_path)
    seen = [str(source_id) for source_id in state.get("processed_source_ids") or [] if str(source_id)]
    seen_set = set(seen)
    changed = False
    for candidate in candidates:
        source_id = canonical_source_id(candidate)
        if source_id and source_id not in seen_set:
            seen.append(source_id)
            seen_set.add(source_id)
            changed = True
    if not changed:
        return state
    state["processed_source_ids"] = seen
    return write_review_state(state_path, state)


def _record_acquisition_results(state_path: Path, acquisition_results: list[Any]) -> dict[str, Any]:
    state = read_review_state(state_path)
    existing = [dict(result) for result in state.get("acquisition_results") or [] if isinstance(result, Mapping)]
    for result in acquisition_results:
        if isinstance(result, Mapping):
            existing.append(dict(result))
    state["acquisition_results"] = existing
    return write_review_state(state_path, state)


def _acquire_candidates(
    config: Mapping[str, Any],
    run_dir: Path,
    *,
    source_provider_kwargs: Mapping[str, Any] | None,
    acquisition_request: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    processed_source_ids = read_review_state(run_dir / "review_state.json").get("processed_source_ids") if (run_dir / "review_state.json").is_file() else []
    request = build_acquisition_request(processed_source_ids=processed_source_ids, acquisition_request=acquisition_request)
    candidates: list[dict[str, Any]] = []
    acquisition_results: list[dict[str, Any]] = []
    for index, source in enumerate(config.get("sources", []) or []):
        provider_id = str(source["provider"])
        provider_config = dict(source.get("config") or {})
        provider_config.setdefault("dataset_config", config)
        provider_config.setdefault("out_dir", str(run_dir / "sources" / f"{index:02d}_{provider_id}"))
        provider_config.setdefault("acquisition_request", copy.deepcopy(request))
        provider_config.setdefault("processed_source_ids", list(request["processed_source_ids"]))
        provider_config.setdefault("exclude_candidate_ids", list(request["exclude_candidate_ids"]))
        provider_config.setdefault("exclude_source_ids", list(request["exclude_source_ids"]))
        provider_config.setdefault("exclude_media_hashes", list(request["exclude_media_hashes"]))
        provider_config.setdefault("feedback_hints", list(request.get("feedback_hints") or []))
        provider_config.setdefault("limit_hint", request["limit_hint"])
        provider = get_source_provider(provider_id, **dict(source_provider_kwargs or {}))
        for candidate in provider.acquire(provider_config):
            candidates.append(_confine_candidate_media(candidate, run_dir))
        result = getattr(provider, "last_acquisition_result", None)
        if isinstance(result, Mapping):
            acquisition_results.append(dict(result))
    if isinstance(config, dict):
        config["_acquisition_results"] = acquisition_results
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
    services = DatasetRunServices.from_config(config)
    return _apply_filter_stages(items, _enabled_filter_stages(config), model_backed=None, services=services)


def _enabled_filter_stages(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    stages = normalize_filter_stages(config).get("filters", {}).get("stages", [])
    return [stage for stage in stages if isinstance(stage, Mapping) and stage.get("enabled") is True]


def _apply_filter_stages(
    items: list[dict[str, Any]],
    stages: list[Mapping[str, Any]],
    *,
    model_backed: bool | None,
    services: DatasetRunServices,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    filter_stats: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = []
    active = items
    for stage in stages:
        if model_backed is not None and bool(stage.get("model_backed")) is not model_backed:
            continue
        stage_id = str(stage.get("stage_id", ""))
        stage_config = stage.get("config") if isinstance(stage.get("config"), Mapping) else {}
        filter_stage = _make_filter_stage(stage_id, services)
        result = filter_stage.apply(active, {}, _stage_runtime_config(stage_config, services))
        active = result.passed
        rejected.extend(result.rejected)
        filter_stats[result.stats["stage_id"]] = result.stats
    return active, rejected, filter_stats


def _make_filter_stage(stage_id: str, services: DatasetRunServices):
    kwargs: dict[str, Any] = {}
    runner = services.filter_stage_runners.get(stage_id)
    if runner is not None:
        kwargs["runner"] = runner
    return services.filter_stage_factory(stage_id, **kwargs)


def _stage_runtime_config(stage_config: Mapping[str, Any], services: DatasetRunServices) -> dict[str, Any]:
    runtime_config = dict(stage_config)
    runtime_config.setdefault("budget_tracker", services.budget_tracker)
    runtime_config.setdefault("clock", services.clock)
    runtime_config.setdefault("sleep", services.sleep)
    if services.artifact_helpers:
        runtime_config.setdefault("artifact_helpers", dict(services.artifact_helpers))
    return runtime_config


def _write_work_preview(
    path: Path,
    config: Mapping[str, Any],
    active_items: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    filter_stats: Mapping[str, Any],
    stages: list[Mapping[str, Any]],
) -> Path:
    model_backed_stages = [
        {
            "stage_id": str(stage.get("stage_id")),
            "enabled": bool(stage.get("enabled", True)),
            "expensive": bool(stage.get("expensive")),
        }
        for stage in stages
        if bool(stage.get("model_backed"))
    ]
    preview = {
        "schema_version": 1,
        "phase": "post_deterministic_filters",
        "active_item_count": len(active_items),
        "rejected_item_count": len(rejected_items),
        "filter_rejected_counts": {
            str(stage_id): int(stats.get("items_rejected", 0))
            for stage_id, stats in filter_stats.items()
            if isinstance(stats, Mapping)
        },
        "filter_warning_counts": {
            str(stage_id): len(stats.get("warnings") or [])
            for stage_id, stats in filter_stats.items()
            if isinstance(stats, Mapping)
        },
        "planned_caption_calls": len(active_items),
        "enabled_model_backed_stages": model_backed_stages,
        "budget_limits": _budget_limits(config),
        "fixture_mode": _fixture_mode(config),
        "expensive_spend_disabled": _expensive_spend_disabled(config),
    }
    _write_json(path, preview)
    return path


def _dry_run_filter_stages(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "stage_id": str(stage.get("stage_id")),
            "enabled": bool(stage.get("enabled", True)),
            "model_backed": bool(stage.get("model_backed")),
            "expensive": bool(stage.get("expensive")),
        }
        for stage in _enabled_filter_stages(config)
    ]


def _budget_limits(config: Mapping[str, Any]) -> dict[str, Any]:
    budgets = config.get("budgets") if isinstance(config.get("budgets"), Mapping) else {}
    return {
        "max_api_calls": budgets.get("max_api_calls"),
        "max_estimated_cost_usd": budgets.get("max_estimated_cost_usd"),
        "providers": copy.deepcopy(dict(budgets.get("providers") or {})),
    }


def _expensive_spend_disabled(config: Mapping[str, Any]) -> bool:
    limits = _budget_limits(config)
    if limits.get("max_api_calls") == 0 or limits.get("max_estimated_cost_usd") == 0:
        return True
    for provider in limits.get("providers", {}).values():
        if isinstance(provider, Mapping) and provider.get("max_calls") == 0:
            return True
    return False


def _fixture_mode(config: Mapping[str, Any]) -> bool:
    extensions = config.get("extensions") or {}
    return isinstance(extensions, Mapping) and extensions.get("fixture_mode") is True


def _write_json(path: Path, payload: Any) -> Path:
    write_json_atomic(path, payload)
    return path


def _caption_items(items: list[dict[str, Any]], config: Mapping[str, Any], run_dir: Path, services: DatasetRunServices) -> list[dict[str, Any]]:
    caption_config = dict(config.get("caption") or {"provider": "visual_understand"})
    caption_config.setdefault("out_dir", str(run_dir / "captions"))
    caption_config.setdefault("budget_tracker", services.budget_tracker)
    caption_config.setdefault("clock", services.clock)
    caption_config.setdefault("sleep", services.sleep)
    if services.artifact_helpers:
        caption_config.setdefault("artifact_helpers", dict(services.artifact_helpers))
    extensions = config.get("extensions") or {}
    if isinstance(extensions, Mapping) and extensions.get("fixture_caption_dir") and "fixture_dir" not in caption_config:
        caption_config["fixture_dir"] = extensions["fixture_caption_dir"]
    if extensions.get("fixture_mode") is True:
        caption_config["fixture_mode"] = True
    captioned: list[dict[str, Any]] = []
    for item in items:
        if services.caption_runner is None:
            result, sidecar = caption_candidate(item, caption_config)
        else:
            result, sidecar = caption_candidate(item, caption_config, runner=services.caption_runner)
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


def _run_human_review(run_dir: Path, review_data_path: Path, state_path: Path, runner, *, media_root: Path | None = None) -> None:
    out_path = run_dir / "review_server" / "human_review.final.json"
    media_dir = media_root or run_dir / "clips"
    cmd = [
        sys.executable,
        "-m",
        "astrid.packs.builtin.executors.human_review.run",
        "--html",
        str(REVIEW_UI_ROOT),
        "--data",
        str(review_data_path),
        "--state",
        str(state_path),
        "--out",
        str(out_path),
        "--serve",
        f"/media={media_dir}",
        "--no-open",
    ]
    runner(cmd, check=True)


def _load_review_decisions(path: str | Path, *, round_index: int = 0) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rounds = payload.get("rounds") if isinstance(payload, Mapping) else None
    if isinstance(rounds, Mapping) and str(round_index) in rounds:
        raw = rounds[str(round_index)]
    elif round_index > 0:
        if not isinstance(rounds, Mapping) or str(round_index) not in rounds:
            raise ValueError(f"non-interactive top-up round {round_index} requires review decisions JSON with rounds.{round_index}")
    else:
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


def _require_review_decisions(decisions: Mapping[str, Any], required_item_ids: set[str], *, round_index: int) -> None:
    missing = sorted(item_id for item_id in required_item_ids if item_id not in decisions)
    if missing:
        raise ValueError(f"round {round_index} review decisions missing required item_ids: {', '.join(missing)}")


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


def _merge_review_decisions(path: Path, decisions: Mapping[str, Mapping[str, Any]], *, submitted: bool) -> dict[str, Any]:
    state = read_review_state(path)
    merged = dict(state.get("review_decisions") or {})
    for item_id, decision in decisions.items():
        merged[str(item_id)] = copy.deepcopy(dict(decision))
    state["review_decisions"] = merged
    state["submitted"] = submitted
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
