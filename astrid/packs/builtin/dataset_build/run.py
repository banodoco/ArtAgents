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

from astrid.core.project.jsonio import write_json_atomic

from .caption_providers import BudgetTracker, caption_candidate
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
from .source_providers import get_source_provider
from .state import make_initial_state, read_review_state, set_status, write_review_state


PACKAGE_ROOT = Path(__file__).resolve().parent
REVIEW_UI_ROOT = PACKAGE_ROOT / "review_ui"


class ResumeConfigMismatchError(ValueError):
    """Raised when an existing run state belongs to a different config."""


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
    human_review_runner=subprocess.run,
    skip_review: bool = False,
    review_only: bool = False,
) -> dict[str, Any]:
    run_dir = Path(out_dir).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(parsed_config.data)
    config.setdefault("output", {})["run_dir"] = str(run_dir)
    _assert_under(run_dir, run_dir)

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
        all_items: list[dict[str, Any]] | None = None
        review_data_path = paths["review_data"]

        if resume_status == "reviewing" and paths["review_data"].is_file():
            all_items = _load_review_data(paths["review_data"])
            captioned = [item for item in all_items if item.get("review_status") != "rejected"]
        else:
            if resume_status in {"preview_ready", "captioning"} and paths["filtered_items"].is_file():
                active_items, rejected_items = _load_filtered_items(paths["filtered_items"])
                filter_stats = dict(read_review_state(state_path).get("filter_stats") or {})
            else:
                candidates = _load_candidates(paths["candidates"]) if paths["candidates"].is_file() else None
                if candidates is None:
                    set_status(state_path, "acquiring")
                    candidates = _phase_acquire_candidates(
                        config,
                        run_dir,
                        paths=paths,
                        state_path=state_path,
                        source_provider_kwargs=source_provider_kwargs,
                    )
                else:
                    _record_processed_sources(state_path, candidates)
                review_items = _phase_prepare_review_items(candidates, config)

                set_status(state_path, "filtering")
                active_items, rejected_items, filter_stats = _phase_deterministic_filters(review_items, config, paths, stages)
                _write_filtered_items(paths["filtered_items"], active_items, rejected_items, phase="post_deterministic_filters")
                _update_state(state_path, {"filter_stats": filter_stats})
                set_status(state_path, "preview_ready")

            if resume_status != "captioning":
                active_items, expensive_rejected, expensive_stats = _phase_model_backed_filters(active_items, config, stages)
                rejected_items.extend(expensive_rejected)
                filter_stats.update(expensive_stats)
                _write_filtered_items(paths["filtered_items"], active_items, rejected_items, phase="post_model_backed_filters")
                _update_state(state_path, {"filter_stats": filter_stats})

            set_status(state_path, "captioning")
            captioned = _phase_caption_items(active_items, config, run_dir, caption_runner=caption_runner)
            all_items = [*captioned, *rejected_items]

            set_status(state_path, "reviewing")
            review_data_path = _phase_prepare_review_data(paths, all_items, config)

        _phase_human_review(
            run_dir,
            state_path,
            review_data_path,
            captioned,
            config,
            review_decisions_path=review_decisions_path,
            human_review_runner=human_review_runner,
            skip_review=skip_review,
        )
        if skip_review and review_decisions_path is None:
            final_state = read_review_state(state_path)
            return {
                "run_dir": str(run_dir),
                "work_preview": str(paths["work_preview"]),
                "review_data": str(review_data_path),
                "review_state": str(state_path),
                "canonical_manifest": None,
                "adapter_manifest": None,
                "accepted": 0,
                "state_status": final_state["status"],
                "state_version": final_state["state_version"],
            }

        canonical_path, adapter_path, canonical = _phase_finalize_manifests(
            run_dir,
            state_path,
            all_items,
            config,
            paths=paths,
            dataset_id=dataset_id,
        )
        set_status(state_path, "finalized")
        final_state = read_review_state(state_path)
        return {
            "run_dir": str(run_dir),
            "work_preview": str(paths["work_preview"]),
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


def _phase_acquire_candidates(
    config: Mapping[str, Any],
    run_dir: Path,
    *,
    paths: Mapping[str, Path],
    state_path: Path,
    source_provider_kwargs: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    candidates = _acquire_candidates(config, run_dir, source_provider_kwargs=source_provider_kwargs)
    _write_json(paths["candidates"], {"candidates": candidates})
    _record_processed_sources(state_path, candidates)
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    active_items, rejected_items, filter_stats = _apply_filter_stages(review_items, stages, model_backed=False)
    _write_work_preview(paths["work_preview"], config, active_items, rejected_items, filter_stats, stages)
    return active_items, rejected_items, filter_stats


def _phase_model_backed_filters(
    active_items: list[dict[str, Any]],
    config: Mapping[str, Any],
    stages: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return _apply_filter_stages(active_items, stages, model_backed=True)


def _phase_caption_items(items: list[dict[str, Any]], config: Mapping[str, Any], run_dir: Path, *, caption_runner) -> list[dict[str, Any]]:
    return _caption_items(items, config, run_dir, caption_runner=caption_runner)


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
    human_review_runner,
    skip_review: bool,
) -> None:
    if review_decisions_path is not None:
        decisions = _load_review_decisions(review_decisions_path)
        _update_state(state_path, {"review_decisions": decisions, "submitted": True})
        write_human_review_final(run_dir, {"review_decisions": decisions, "submitted": True})
    elif skip_review:
        return
    elif (config.get("review") or {}).get("enabled", True):
        _run_human_review(run_dir, review_data_path, state_path, human_review_runner)
    else:
        decisions = _accept_all_decisions(captioned)
        _update_state(state_path, {"review_decisions": decisions, "submitted": True})
        write_human_review_final(run_dir, {"review_decisions": decisions, "submitted": True})


def _phase_finalize_manifests(
    run_dir: Path,
    state_path: Path,
    all_items: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    paths: Mapping[str, Path],
    dataset_id: str,
) -> tuple[Path, Path, dict[str, Any]]:
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
        "human_review_final": run_dir / "review_server" / "human_review.final.json",
    }


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


def _acquire_candidates(config: Mapping[str, Any], run_dir: Path, *, source_provider_kwargs: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    processed_source_ids = read_review_state(run_dir / "review_state.json").get("processed_source_ids") if (run_dir / "review_state.json").is_file() else []
    candidates: list[dict[str, Any]] = []
    for index, source in enumerate(config.get("sources", []) or []):
        provider_id = str(source["provider"])
        provider_config = dict(source.get("config") or {})
        provider_config.setdefault("dataset_config", config)
        provider_config.setdefault("out_dir", str(run_dir / "sources" / f"{index:02d}_{provider_id}"))
        provider_config.setdefault("processed_source_ids", list(processed_source_ids or []))
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
    return _apply_filter_stages(items, _enabled_filter_stages(config), model_backed=None)


def _enabled_filter_stages(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    stages = normalize_filter_stages(config).get("filters", {}).get("stages", [])
    return [stage for stage in stages if isinstance(stage, Mapping) and stage.get("enabled") is True]


def _apply_filter_stages(
    items: list[dict[str, Any]],
    stages: list[Mapping[str, Any]],
    *,
    model_backed: bool | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    filter_stats: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = []
    active = items
    for stage in stages:
        if model_backed is not None and bool(stage.get("model_backed")) is not model_backed:
            continue
        stage_id = str(stage.get("stage_id", ""))
        stage_config = stage.get("config") if isinstance(stage.get("config"), Mapping) else {}
        filter_stage = get_filter_stage(stage_id)
        result = filter_stage.apply(active, {}, dict(stage_config))
        active = result.passed
        rejected.extend(result.rejected)
        filter_stats[result.stats["stage_id"]] = result.stats
    return active, rejected, filter_stats


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
