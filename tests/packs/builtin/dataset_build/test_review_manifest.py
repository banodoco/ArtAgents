from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astrid.packs.builtin.dataset_build.manifest import build_canonical_manifest, validate_schema, write_canonical_manifest
from astrid.packs.builtin.dataset_build.manifest_adapters import get_manifest_adapter
from astrid.packs.builtin.dataset_build.manifest_adapters.ai_toolkit_ltx import AiToolkitLtxAdapter
from astrid.packs.builtin.dataset_build.review import (
    apply_review_decisions,
    write_human_review_final,
    write_initial_review_state,
    write_review_data,
)
from astrid.packs.builtin.dataset_build.state import read_review_state


def _item(tmp_path: Path, item_id: str, *, bucket: str = "wide") -> dict[str, Any]:
    media = tmp_path / f"{item_id}.mp4"
    media.write_bytes(f"media-{item_id}".encode("utf-8"))
    return {
        "item_id": item_id,
        "source_type": "local_folder",
        "source_id": "source-1",
        "source_url": media.as_uri(),
        "source_metadata": {"resolution": {"width": 128, "height": 128}},
        "rights": {"license": "unknown", "attribution": "", "restrictions": [], "rights_status": "unknown"},
        "content_hash": "a" * 64,
        "acquired_at": "2026-05-21T00:00:00Z",
        "media_type": "video",
        "media_path": str(media),
        "duration_s": 5.0,
        "clip_start_s": 0.0,
        "clip_end_s": 5.0,
        "scene_index": 0,
        "bucket": bucket,
        "caption": {"text": f"Original caption {item_id}", "schema_version": 1, "confidence": 0.8, "model": "fixture"},
        "caption_file": str(tmp_path / "old" / f"{item_id}.caption.json"),
        "filter_results": {"duration_filter": {"passed": True, "reason": "", "score": 5.0}},
        "review_status": "pending",
    }


def _state() -> dict[str, Any]:
    return {
        "state_version": 4,
        "review_decisions": {
            "clip-a": {
                "item_id": "clip-a",
                "decision": "accept",
                "reject_reason": None,
                "edited_caption": "Edited accepted caption.",
                "reviewed_at": "2026-05-21T00:01:00Z",
                "reviewer_id": "reviewer",
                "state_version": 4,
            },
            "clip-b": {
                "item_id": "clip-b",
                "decision": "reject",
                "reject_reason": "low_quality",
                "edited_caption": None,
                "reviewed_at": "2026-05-21T00:02:00Z",
                "state_version": 4,
            },
        },
    }


def test_review_application_persists_edited_caption_sidecars_and_statuses(tmp_path: Path) -> None:
    items = [_item(tmp_path, "clip-a"), _item(tmp_path, "clip-b"), _item(tmp_path, "clip-c")]

    reviewed = apply_review_decisions(items, _state(), now="2026-05-21T00:03:00Z")

    by_id = {item["item_id"]: item for item in reviewed}
    assert by_id["clip-a"]["review_status"] == "accepted"
    assert by_id["clip-a"]["caption"]["text"] == "Edited accepted caption."
    assert by_id["clip-a"]["review_decision"]["decision"] == "accept"
    assert by_id["clip-b"]["review_status"] == "rejected"
    assert by_id["clip-b"]["review_decision"]["reject_reason"] == "low_quality"
    assert by_id["clip-c"]["review_status"] == "pending"
    sidecar = tmp_path / "clip-a.caption.json"
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["text"] == "Edited accepted caption."
    assert sidecar_payload["hashes"]["media_hash"] == "a" * 64
    assert sidecar_payload["hashes"]["prompt_hash"]
    assert by_id["clip-a"]["caption_file"] == str(sidecar)


def test_review_application_preserves_existing_caption_hash_metadata(tmp_path: Path) -> None:
    item = _item(tmp_path, "clip-a")
    old_sidecar = tmp_path / "old" / "clip-a.caption.json"
    old_sidecar.parent.mkdir()
    old_sidecar.write_text(
        json.dumps(
            {
                "text": "Original caption clip-a",
                "schema_version": 1,
                "confidence": 0.8,
                "model": "fixture",
                "hashes": {
                    "prompt_hash": "prompt",
                    "schema_hash": "schema",
                    "media_hash": "media",
                    "config_hash": "config",
                },
            }
        ),
        encoding="utf-8",
    )
    item["caption_file"] = str(old_sidecar)

    reviewed = apply_review_decisions([item], _state(), now="2026-05-21T00:03:00Z")

    sidecar = tmp_path / "clip-a.caption.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert reviewed[0]["caption"]["text"] == "Edited accepted caption."
    assert payload["text"] == "Edited accepted caption."
    assert payload["hashes"] == {
        "config_hash": "config",
        "media_hash": "media",
        "prompt_hash": "prompt",
        "schema_hash": "schema",
    }


def test_canonical_and_ai_toolkit_manifests_include_only_accepted_items_and_validate(tmp_path: Path) -> None:
    reviewed = apply_review_decisions([_item(tmp_path, "clip-a"), _item(tmp_path, "clip-b")], _state())
    canonical = build_canonical_manifest(
        reviewed,
        dataset_id="dataset-fixture",
        source_provider="local_folder",
        bucket_targets={"wide": 2},
        created_at="2026-05-21T00:04:00Z",
    )
    canonical_path = write_canonical_manifest(tmp_path / "final.manifest.json", canonical)

    assert [item["item_id"] for item in canonical["items"]] == ["clip-a"]
    assert canonical["stats"]["total_accepted"] == 1
    assert canonical["stats"]["total_rejected"] == 1
    validate_schema(canonical, "manifest.schema.json")

    adapter = AiToolkitLtxAdapter(
        out_path=tmp_path / "ai-toolkit-ltx.manifest.json",
        source_manifest=canonical_path,
        repo_root=tmp_path,
    )
    adapter_path = adapter.export(canonical["items"])
    payload = json.loads(adapter_path.read_text(encoding="utf-8"))

    assert len(payload["clips"]) == 1
    clip = payload["clips"][0]
    assert clip["clip_id"] == "clip-a"
    assert clip["clip_file"].endswith("clip-a.mp4")
    assert clip["caption_file"].endswith("clip-a.caption.json")
    assert clip["caption_file"] == "clip-a.caption.json"
    validate_schema(payload, "ai-toolkit-adapter-manifest.schema.json")


def test_ai_toolkit_adapter_enforces_existing_clip_and_sibling_caption_sidecar(tmp_path: Path) -> None:
    item = _item(tmp_path, "clip-a")
    item["review_status"] = "accepted"
    non_sibling = tmp_path / "captions" / "clip-a.caption.json"
    non_sibling.parent.mkdir()
    non_sibling.write_text("{}", encoding="utf-8")
    item["caption_file"] = str(non_sibling)

    adapter = AiToolkitLtxAdapter(out_path=tmp_path / "out.json", repo_root=tmp_path)
    assert adapter.validate([item]) == ["clip-a: caption sidecar must be sibling clip-a.caption.json"]

    item["caption_file"] = str(tmp_path / "clip-a.caption.json")
    assert adapter.validate([item]) == ["clip-a: caption sidecar missing: " + str(tmp_path / "clip-a.caption.json")]

    Path(item["caption_file"]).write_text("{}", encoding="utf-8")
    item["media_path"] = str(tmp_path / "missing.mp4")
    assert adapter.validate([item]) == ["clip-a: clip path missing: " + str(tmp_path / "missing.mp4")]


def test_review_artifact_writers_create_review_data_state_and_final_payload(tmp_path: Path) -> None:
    items = [_item(tmp_path, "clip-a")]
    review_data = write_review_data(tmp_path / "review_data.json", items)
    state = write_initial_review_state(
        tmp_path / "review_state.json",
        run_id="run-1",
        writer_id="writer-1",
        buckets={"wide": 1},
        now="2026-05-21T00:00:00Z",
    )
    final = write_human_review_final(tmp_path, {"submitted": True, "items": [{"item_id": "clip-a"}]})

    assert json.loads(review_data.read_text(encoding="utf-8"))["items"][0]["item_id"] == "clip-a"
    assert state["state_version"] == 1
    assert read_review_state(tmp_path / "review_state.json")["status"] == "reviewing"
    assert final == tmp_path / "review_server" / "human_review.final.json"
    assert json.loads(final.read_text(encoding="utf-8")) == {"items": [{"item_id": "clip-a"}], "submitted": True}


def test_manifest_adapter_registry() -> None:
    assert isinstance(get_manifest_adapter("ai-toolkit-ltx"), AiToolkitLtxAdapter)
    with pytest.raises(ValueError, match="unknown manifest adapter"):
        get_manifest_adapter("other")
