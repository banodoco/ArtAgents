"""Assertions for the isolated Intro generation-to-render bridge proof."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

EVIDENCE = Path(
    os.environ.get(
        "BRIDGE_EVIDENCE_DIR",
        "/Volumes/ASTRID_RAM/generation-render-bridge-20260901/evidence",
    )
)
REQUIRED = (
    "admission.json",
    "public-read-trace.json",
    "candidate-before-promotion.json",
    "promotion.json",
    "invalidation.json",
    "refresh.json",
    "timeline-render.json",
    "custody-before.json",
    "custody-after.json",
    "intro-proof.json",
    "artifact-hashes.json",
)


def _load(name: str) -> dict:
    path = EVIDENCE / name
    if not path.exists():
        pytest.skip("run the bridge proof first")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_packet_has_all_named_evidence_files() -> None:
    missing = [name for name in REQUIRED if not (EVIDENCE / name).is_file()]
    if missing:
        pytest.skip(f"run the bridge proof first; missing {missing}")
    proof = _load("intro-proof.json")
    assert proof["schema"] == "astrid.intro.generation-render-bridge-proof/v1"
    assert proof["criteria"] == {f"C{i}": True for i in range(1, 9)}


def test_admission_and_public_reads_preserve_frozen_recipe() -> None:
    admission = _load("admission.json")
    trace = _load("public-read-trace.json")
    recipe = admission["recipe"]
    assert admission["output_count"] == 2
    assert recipe["schema"] == "astrid.shot-generation-recipe/v1"
    assert recipe["target_role"] == "primary_visual"
    assert recipe["prompt_binding"]["head"] >= 0
    assert len(recipe["prompt_binding"]["content_sha256"]) == 64
    assert [entry["ordinal"] for entry in recipe["inputs"]] == [0, 1]
    assert all(len(entry["content_sha256"]) == 64 for entry in recipe["inputs"])
    assert len(recipe["parent_content_sha256"]) == 64
    assert trace["task"]["spec"] == admission["spec"]
    assert trace["run"]["child_outputs"][0]["outputs"]
    assert all(media["id"] for media in trace["media"])
    assert all(media["relations"] for media in trace["media"])


def test_candidates_are_isolated_before_explicit_promotion() -> None:
    before = _load("candidate-before-promotion.json")
    statuses = [
        item["metadata"].get("status") for item in before["candidates"]
    ]
    assert statuses == ["candidate", "candidate"]
    assert before["primary_item_id"] not in {
        item["id"] for item in before["candidates"]
    }
    assert before["primary_media_id"] not in {
        item["media_id"] for item in before["candidates"]
    }


def test_promotion_replay_retains_history_and_derives_invalidation() -> None:
    proof = _load("intro-proof.json")
    promotion = _load("promotion.json")
    invalidation = _load("invalidation.json")
    assert promotion["promotion"]["candidate_item_id"] == proof["promotion"]["selected_candidate_item_id"]
    assert proof["promotion"]["replay_identical"] is True
    stale = {entry.get("item_id") or entry.get("asset_id") for entry in invalidation["stale"]}
    assert {entry["item_id"] for entry in invalidation["stale"] if entry.get("kind") in {"plate", "proxy"}}
    assert "timeline-shot-02" in stale
    assert any(entry["kind"] == "generative_transition" for entry in invalidation["blocked_on_generation"])
    assert invalidation["ready_to_compile"] == []


def test_refresh_is_selective_and_does_not_regenerate_transition() -> None:
    refresh = _load("refresh.json")
    assert refresh["rebuild_counts"] == {"numbered_review_proxies": 1, "plates": 1}
    assert refresh["plate"]["before_item_id"] != refresh["plate"]["after_item_id"]
    assert refresh["proxy"]["before_item_id"] != refresh["proxy"]["after_item_id"]
    assert refresh["unchanged"]["generative_transition_unchanged"] is True
    assert refresh["selected_candidate"]["content_sha256"]


def test_timeline_save_render_and_provenance_pin_selected_candidate() -> None:
    timeline = _load("timeline-render.json")
    render = timeline["render"]
    assert timeline["timeline"]["saved_version"] == timeline["timeline"]["created_version"] + 1
    selected = timeline["selected_candidate"]
    asset = timeline["timeline"]["save"]["registry"]["assets"]["plate_two_ideas"]
    assert asset["generationId"] == selected["item_id"]
    assert asset["variantId"] == selected["media_id"]
    assert len(selected["content_sha256"]) == 64
    assert render["output_sha256"] == render["artifact"]["content_hash"]
    assert Path(render["managed_path"]).is_file()
    assert Path(render["review_path"]).is_file()
    assert _sha256(Path(render["review_path"])) == render["output_sha256"]
    assert {stream["codec_name"] for stream in render["streams"]} >= {"h264", "aac"}
    assert render["provenance"]["canonical_timeline"]["authority"] == "kernel"
    assert render["provenance"]["canonical_timeline"]["config_version"] == timeline["timeline"]["saved_version"]


def test_custody_and_artifact_hashes_are_exact() -> None:
    proof = _load("intro-proof.json")
    before = json.loads((EVIDENCE / "custody-before.json").read_text(encoding="utf-8"))
    after = json.loads((EVIDENCE / "custody-after.json").read_text(encoding="utf-8"))
    hashes = _load("artifact-hashes.json")
    assert proof["custody_equal"] is True
    assert before == after
    assert hashes["design_source_sha256"] == hashes["design_canonical_sha256"]
    assert hashes["design_canonical_sha256"] == "aac23cc0a47d3dded05b5e0fb8fc3d30fdfc15119fa583e4ffd318dc6afe5639"
    assert hashes["intro-proof"] == _sha256(EVIDENCE / "intro-proof.json")
