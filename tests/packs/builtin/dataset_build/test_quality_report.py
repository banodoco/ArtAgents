from __future__ import annotations

from astrid.packs.training.orchestrators.dataset_build.reports.quality_report import build_quality_report


def test_quality_report_contains_required_sections() -> None:
    items = [
        {
            "item_id": "accepted-1",
            "source_id": "source-a",
            "source_url": "file:///source-a.mp4",
            "content_hash": "a" * 64,
            "bucket": "wide",
            "review_status": "accepted",
            "filter_results": {
                "semantic_visual_filter": {"passed": True, "score": 0.82, "reason": "useful"},
            },
        },
        {
            "item_id": "rejected-1",
            "source_id": "source-a",
            "source_url": "file:///source-a.mp4",
            "content_hash": "b" * 64,
            "bucket": "wide",
            "review_status": "rejected",
            "rights": {"rights_status": "unknown"},
            "filter_results": {
                "duration_filter": {"passed": False, "reason": "duration_too_short"},
            },
        },
    ]
    state = {
        "status": "failed",
        "filter_stats": {"duration_filter": {"items_rejected": 1}},
        "caption_validation_failures": [{"item_id": "accepted-1", "code": "caption_text_empty", "message": "empty"}],
        "acquisition_results": [{"provider": "local_folder", "round_index": 1, "yielded": 0}],
    }

    report = build_quality_report(
        items=items,
        config={"dataset_id": "fixture", "buckets": {"wide": {"target_count": 2}}},
        state=state,
        budget={"total_api_calls": 3, "observed_calls_by_provider": {"caption.visual_understand": 1}},
        final_shortfalls={"wide": 1},
    )

    assert report["source_concentration"]["sources"] == [{"source_id": "source-a", "count": 2}]
    assert report["rights_provenance_warnings"][0]["code"] == "rights_not_verified"
    assert report["budget_observed_counts"]["total_api_calls"] == 3
    assert report["bucket_counts"]["wide"]["accepted"] == 1
    assert report["filter_rejection_breakdowns"]["by_stage_reason"]["duration_filter"] == {"duration_too_short": 1}
    assert report["semantic_scores"][0]["score"] == 0.82
    assert report["caption_validation_failures"][0]["code"] == "caption_text_empty"
    assert report["top_up_acquisition_results"][0]["round_index"] == 1
    assert report["final_shortfalls"] == {"wide": 1}
