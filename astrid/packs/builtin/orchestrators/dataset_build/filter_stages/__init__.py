"""Filter stage implementations for builtin.dataset_build."""

from __future__ import annotations

from typing import Any

from ._common import (
    build_filter_stats,
    canonical_source_id,
    increment_reason,
    nested_metadata,
    pass_item,
    record_warning,
    reject_item,
    resolve_media_path,
    with_filter_result,
)
from .bucket_judge import BucketJudgeGate, judge_sidecar_path
from .black_frame import BlackFrameFilter
from .content_hash import ContentHashFilter
from .duration import DurationFilter
from .near_duplicate import NearDuplicateFilter
from .resolution import ResolutionFilter
from .rights import RightsFilter
from .semantic import SemanticVideoFilter, SemanticVisualFilter, semantic_sidecar_path
from .source_cap import SourceCapFilter
from .transcript_keyword import TranscriptKeywordFilter, transcript_sidecar_path


STAGES = {
    "duration_filter": DurationFilter,
    "resolution_filter": ResolutionFilter,
    "black_frame_filter": BlackFrameFilter,
    "content_hash_filter": ContentHashFilter,
    "source_cap_filter": SourceCapFilter,
    "rights_filter": RightsFilter,
    "bucket_judge_filter": BucketJudgeGate,
    "transcript_keyword_filter": TranscriptKeywordFilter,
    "semantic_visual_filter": SemanticVisualFilter,
    "semantic_video_filter": SemanticVideoFilter,
    "near_duplicate_filter": NearDuplicateFilter,
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
    "BlackFrameFilter",
    "ContentHashFilter",
    "DurationFilter",
    "NearDuplicateFilter",
    "ResolutionFilter",
    "RightsFilter",
    "SemanticVideoFilter",
    "SemanticVisualFilter",
    "STAGES",
    "SourceCapFilter",
    "build_filter_stats",
    "canonical_source_id",
    "get_filter_stage",
    "increment_reason",
    "judge_sidecar_path",
    "nested_metadata",
    "pass_item",
    "record_warning",
    "reject_item",
    "resolve_media_path",
    "semantic_sidecar_path",
    "TranscriptKeywordFilter",
    "transcript_sidecar_path",
    "with_filter_result",
]
