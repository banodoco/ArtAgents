"""Filter stage implementations for builtin.dataset_build."""

from __future__ import annotations

from typing import Any

from .bucket_judge import BucketJudgeGate, judge_sidecar_path
from .duration import DurationFilter


STAGES = {
    "duration_filter": DurationFilter,
    "bucket_judge_filter": BucketJudgeGate,
}


def get_filter_stage(stage_id: str, **kwargs: Any):
    try:
        stage_cls = STAGES[stage_id]
    except KeyError as exc:
        available = ", ".join(sorted(STAGES))
        raise ValueError(f"unknown filter stage {stage_id!r}; available stages: {available}") from exc
    return stage_cls(**kwargs)


__all__ = [
    "BucketJudgeGate",
    "DurationFilter",
    "STAGES",
    "get_filter_stage",
    "judge_sidecar_path",
]
