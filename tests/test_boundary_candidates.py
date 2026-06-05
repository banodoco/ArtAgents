from __future__ import annotations

import json

from astrid.packs.editorial.executors.boundary_candidates.run import main


def test_boundary_candidates_packages_asset_level_refs(tmp_path):
    manifest = tmp_path / "talks.json"
    transcript = tmp_path / "transcript.json"
    scenes = tmp_path / "scenes.json"
    shots = tmp_path / "shots.json"
    holding = tmp_path / "holding.json"
    out = tmp_path / "boundary-candidates.json"

    manifest.write_text(
        json.dumps(
            {
                "talks": [
                    {
                        "slug": "speaker-talk",
                        "speaker": "Speaker",
                        "title": "Talk",
                        "start": 100.0,
                        "end": 200.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    transcript.write_text(
        json.dumps({"segments": [{"start": 96.0, "end": 104.0, "text": "Hello everyone."}]}),
        encoding="utf-8",
    )
    scenes.write_text(json.dumps([{"index": 7, "start": 90.0, "end": 110.0, "duration": 20.0}]), encoding="utf-8")
    shots.write_text(json.dumps([{"scene_index": 7, "frames": []}]), encoding="utf-8")
    holding.write_text(json.dumps({"intervals": [{"start": 80.0, "end": 95.0, "matched": ["break"]}]}), encoding="utf-8")

    code = main(
        [
            "--video",
            "source.mp4",
            "--asset-key",
            "main",
            "--manifest",
            str(manifest),
            "--transcript",
            str(transcript),
            "--scenes",
            str(scenes),
            "--shots",
            str(shots),
            "--holding-screens",
            str(holding),
            "--out",
            str(out),
            "--kind",
            "start",
            "--window",
            "30",
        ]
    )

    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["asset_key"] == "main"
    assert payload["asset_analysis"]["scenes"] == str(scenes)
    assert payload["metadata_source_refs"]["main"]["transcript_ref"] == str(transcript)
    assert payload["metadata_source_refs"]["main"]["scenes_ref"] == str(scenes)
    assert payload["metadata_source_refs"]["main"]["shots_ref"] == str(shots)
    assert payload["metadata_source_refs"]["main"]["holding_screens_ref"] == str(holding)
    assert payload["metadata_source_refs"]["main"]["boundary_candidates_ref"] == str(out)
    boundary = payload["boundaries"][0]
    assert boundary["kind"] == "start"
    assert any("scene_start" in item["reasons"] for item in boundary["candidates"])
    assert any("transcript_start" in item["reasons"] for item in boundary["candidates"])

    manifest_path = out.parent / "manifest.json"
    assert manifest_path.is_file(), f"manifest not found at {manifest_path}"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["kind"] == "boundary_candidates"
    assert manifest_payload["schema_version"] == 1
    assert isinstance(manifest_payload["inputs"], dict)
    assert "video" in manifest_payload["inputs"]
    assert "manifest" in manifest_payload["inputs"]
    assert isinstance(manifest_payload["outputs"], list)
    assert len(manifest_payload["outputs"]) == 1
    assert manifest_payload["outputs"][0]["path"] == out.name
    assert isinstance(manifest_payload["warnings"], list)
