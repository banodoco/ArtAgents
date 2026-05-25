from __future__ import annotations

import json
from pathlib import Path

from astrid.packs.training.orchestrators.dataset_build.artifacts import sidecar_hashes, write_hashed_sidecar
from astrid.packs.training.orchestrators.dataset_build.caption_validation import validate_accepted_captions
from astrid.packs.training.orchestrators.dataset_build.items import make_candidate_item


def _accepted_item(tmp_path: Path) -> dict:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fixture-media")
    item = {
        **make_candidate_item(
            source_type="local_folder",
            source_id="source-1",
            source_url=media.as_uri(),
            media_path=media,
            media_type="video",
            source_metadata={"resolution": {"width": 64, "height": 64}},
            duration_s=5.0,
            clip_start_s=0.0,
            clip_end_s=5.0,
            scene_index=0,
        ),
        "item_id": "clip-a",
        "review_status": "accepted",
        "caption": {
            "text": "APPROVED: useful clip",
            "schema_version": 1,
            "confidence": 0.9,
            "model": "stub",
            "raw_response": {"label": "ok"},
        },
    }
    sidecar = tmp_path / "clip-a.caption.json"
    hashes = sidecar_hashes(prompt="", schema=1, media=item, config={"caption_model": "stub"})
    write_hashed_sidecar(sidecar, item["caption"], hashes)
    item["caption_file"] = str(sidecar)
    return item


def test_validate_accepted_captions_accepts_hashed_sidecar_schema_and_text_rules(tmp_path: Path) -> None:
    schema = tmp_path / "caption-response.schema.json"
    schema.write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["label"],
                "properties": {"label": {"const": "ok"}},
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )

    result = validate_accepted_captions(
        [_accepted_item(tmp_path)],
        {"caption": {"schema_path": str(schema), "validation": {"text_pattern": "^APPROVED:", "min_length": 10}}},
        now="2026-05-21T00:00:00Z",
    )

    assert result.failures == []
    assert "caption_validation" not in result.items[0]


def test_validate_accepted_captions_rejects_raw_sidecar_and_bad_text(tmp_path: Path) -> None:
    item = _accepted_item(tmp_path)
    sidecar = Path(item["caption_file"])
    sidecar.write_text(
        json.dumps({"text": "bad", "schema_version": 1, "confidence": 0.9, "model": "stub"}),
        encoding="utf-8",
    )
    item["caption"]["text"] = "bad"

    result = validate_accepted_captions(
        [item],
        {"caption": {"validation": {"text_pattern": "^APPROVED:"}}},
        now="2026-05-21T00:00:00Z",
    )

    assert [failure["code"] for failure in result.failures] == [
        "caption_sidecar_schema_error",
        "caption_text_pattern_mismatch",
    ]
    validation = result.items[0]["caption_validation"]
    assert validation["valid"] is False
    assert validation["failures"][0]["path"] == "hashes"
