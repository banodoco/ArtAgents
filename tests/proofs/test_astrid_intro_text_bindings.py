"""Focused assertions for the isolated Astrid Intro B4 proof packet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EVIDENCE = Path(__file__).resolve().parents[5] / ".otto/runs/timeline-text-workstream-20260831/evidence/intro"


def _proof() -> dict:
    path = EVIDENCE / "intro-proof.json"
    if not path.exists():
        pytest.skip("run scripts/proofs/astrid_intro_text_bindings.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def test_snapshot_packet_has_custody_equality() -> None:
    proof = _proof()
    assert proof["custody_equal"] is True
    before = json.loads((EVIDENCE / "custody-before.json").read_text())
    after = json.loads((EVIDENCE / "custody-after.json").read_text())
    assert before == after
    wal = next((v for p, v in before.items() if p.endswith("-wal")), None)
    assert wal is None or wal["size"] == 0


def test_bootstrap_counts_and_targets_are_text() -> None:
    proof = _proof()
    assert proof["counts"] == {"bindings": 76, "caption_plates": 24, "shots": 25, "visuals": 26, "wav": 25}
    data = json.loads((EVIDENCE / "bootstrap-bindings.json").read_text())
    assert data["counts"] == {"prompt": 26, "transcript": 25, "voiceover_script": 25}
    assert data["variant_count"] == 51
    assert data["canonical_prompt_count"] == 25
    assert data["deduped_prompt_count"] == 26
    assert data["regen_glitch_slots"] == ["ex_glitch/regen-glitch"]
    hashes = json.loads((EVIDENCE / "authored-byte-hashes.json").read_text())
    assert len(hashes) == 76
    assert all(len(value) == 64 and value == value.lower() for value in hashes.values())


def test_recipe_and_lineage_are_directional() -> None:
    proof = _proof()
    assert proof["recipe"]["id"] == "astrid-intro-captioned-plate/v1"
    assert len(proof["recipe"]["digest"]) == 64
    assert proof["lineage"] == {"active_plate_to_transcript": 24, "active_plate_to_visual": 24, "reversed_transcript_to_plate": 0}


def test_controlled_edit_changes_only_video() -> None:
    proof = _proof()
    renders = proof["renders"]
    assert renders["baseline"]["framemd5_sha256"] == renders["unchanged"]["framemd5_sha256"]
    assert renders["baseline"]["pcm_sha256"] == renders["unchanged"]["pcm_sha256"]
    assert renders["baseline"]["framemd5_sha256"] != renders["edited"]["framemd5_sha256"]
    assert renders["baseline"]["pcm_sha256"] == renders["edited"]["pcm_sha256"]


def test_media_only_timeline_and_opening_wording() -> None:
    proof = _proof()
    assert proof["timeline_contract"] == {"clip_types": ["media"], "separate_wordmark_or_text_overlay_clips": 0, "visual_tracks": 1}
    assert proof["opening"]["source_relative"] == "build/h3/push-3s.mp4"
    assert proof["opening"]["embedded_logo_pixels"].startswith("preserved")
    assert proof["builder_entrypoints"] == {"main_called": False, "materialize_render_plates_called": False}
    bootstrap = json.loads((EVIDENCE / "bootstrap-bindings.json").read_text())
    prior = next(item for item in bootstrap["bindings"] if item["binding_id"] == proof["controlled_edit"]["binding_id"])
    assert proof["controlled_edit"]["new_media_id"] != prior["media_id"]
    assert proof["controlled_edit"]["descriptor"]["transcript_media_id"] == proof["controlled_edit"]["new_media_id"]
