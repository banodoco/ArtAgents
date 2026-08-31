from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from astrid import audit
from astrid.core.audit import AuditContext


def test_audit_collects_ephemeral_provenance_without_ledger(tmp_path: Path) -> None:
    run = tmp_path / "run"
    artifact = run / "frames" / "frame.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("hello audit", encoding="utf-8")

    ctx = AuditContext.for_run(run)
    source_id = ctx.register_asset(kind="source", path=artifact, label="Source")
    output_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[source_id])
    ctx.register_node(stage="demo", parents=[source_id], outputs=[output_id])

    assert [row["asset_id"] for row in ctx.records if "asset_id" in row] == [source_id, output_id]
    assert not (run / "audit" / "ledger.jsonl").exists()


def test_ephemeral_provenance_ids_are_stable(tmp_path: Path) -> None:
    run = tmp_path / "run"
    artifact = run / "asset.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("v1", encoding="utf-8")
    ctx = AuditContext.for_run(run)
    parent_id = ctx.register_asset(kind="source", label="Source")
    first_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[parent_id])
    artifact.write_text("v2", encoding="utf-8")
    second_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[parent_id])

    assert first_id == second_id
    assert len(ctx.records) == 3
    assert not (run / "audit" / "ledger.jsonl").exists()


def test_audit_redacts_secret_like_values(tmp_path: Path) -> None:
    ctx = AuditContext.for_run(tmp_path / "run")
    ctx.register_node(
        stage="secret-test",
        metadata={"OPENAI_API_KEY": "sk-testsecret1234567890", "nested": {"token": "hf_abcdefghijklmnop"}},
    )
    event = ctx.records[0]
    assert event["metadata"]["OPENAI_API_KEY"] == "<redacted>"
    assert event["metadata"]["nested"]["token"] == "<redacted>"


def test_pipeline_audit_cli_is_retired() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("astrid.core.audit.cli")


def test_pipeline_audit_env_propagation_and_fallback(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("jsonschema")
    from astrid.packs.video_editing.orchestrators.hype import run as pipeline

    script = tmp_path / "child.py"
    script.write_text(
        "import os, pathlib\n"
        "out = pathlib.Path(os.environ['CHILD_OUT'])\n"
        "out.write_text(os.environ.get('ASTRID_AUDIT_RUN_DIR', ''), encoding='utf-8')\n",
        encoding="utf-8",
    )
    out = tmp_path / "run"
    args = type(
        "Args",
        (),
        {
            "out": out,
            "brief_out": out,
            "verbose": False,
            "audit": AuditContext.for_run(out),
            "no_audit": False,
            "extra_args": {},
        },
    )()
    monkeypatch.setenv("CHILD_OUT", str(out / "sentinel.txt"))
    step = pipeline.Step("demo", ("sentinel.txt",), lambda _: [sys.executable, str(script)])

    assert pipeline.run_step(step, step.build_cmd(args), args) == 0
    assert (out / "sentinel.txt").read_text(encoding="utf-8") == str(out)
    assert not (out / "audit" / "ledger.jsonl").exists()


def test_ambient_register_outputs_from_producer(monkeypatch, tmp_path: Path) -> None:
    from astrid.packs.editorial.executors.scenes import run as scenes

    run = tmp_path / "run"
    monkeypatch.setenv("ASTRID_AUDIT_RUN_DIR", str(run))
    json_path = run / "scenes.json"
    csv_path = run / "scenes.csv"

    scenes.write_outputs([{"index": 1, "start": 0.0, "end": 1.0, "duration": 1.0}], json_path, csv_path)

    assert not (run / "audit" / "ledger.jsonl").exists()


def test_ambient_register_outputs_inherits_parent_ids(monkeypatch, tmp_path: Path) -> None:
    from astrid.packs.editorial.executors.scenes import run as scenes

    run = tmp_path / "run"
    parent_id = "source-parent"
    monkeypatch.setenv("ASTRID_AUDIT_RUN_DIR", str(run))
    monkeypatch.setenv("ASTRID_AUDIT_PARENT_IDS", parent_id)

    scenes.write_outputs([{"index": 1, "start": 0.0, "end": 1.0, "duration": 1.0}], run / "scenes.json", run / "scenes.csv")

    assert not (run / "audit" / "ledger.jsonl").exists()


def test_shots_writes_universal_result_manifest(tmp_path: Path) -> None:
    """editorial.shots writes manifest.json with kind=shots, scenes input, and shots.json."""
    from unittest.mock import patch

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    scenes_path = tmp_path / "scenes.json"
    scenes_path.write_text(
        json.dumps([{"index": 1, "start": 0.0, "end": 10.0, "duration": 10.0}]),
        encoding="utf-8",
    )
    video_path = tmp_path / "video.mp4"
    video_path.write_text("fake video", encoding="utf-8")

    def fake_extract_frame(video: Path, timestamp: float, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("fake jpg", encoding="utf-8")

    with patch(
        "astrid.packs.editorial.executors.shots.run.extract_frame",
        side_effect=fake_extract_frame,
    ):
        from astrid.packs.editorial.executors.shots.run import main

        ret = main(
            [
                "--video", str(video_path),
                "--scenes", str(scenes_path),
                "--out", str(out_dir),
                "--per-scene", "1",
            ]
        )
        assert ret == 0

    # Verify shots.json is preserved with original shape
    shots_data = json.loads((out_dir / "shots.json").read_text(encoding="utf-8"))
    assert isinstance(shots_data, list)
    assert len(shots_data) == 1
    assert shots_data[0]["scene_index"] == 1
    assert "frames" in shots_data[0]

    # Verify manifest.json
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file(), f"manifest.json not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "shots"
    assert manifest["inputs"]["video"] == str(video_path)
    assert manifest["inputs"]["scenes"] == str(scenes_path)
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 1
    assert manifest["outputs"][0]["type"] == "file"
    assert "shots.json" in manifest["outputs"][0]["path"]
    assert "content_hash" in manifest["outputs"][0]
    assert "bytes" in manifest["outputs"][0]
    assert isinstance(manifest["warnings"], list)
    assert "created" in manifest

def test_transcribe_writes_universal_result_manifest(tmp_path: Path, monkeypatch) -> None:
    """editorial.transcribe writes manifest.json with kind=transcript, audio input, and transcript files."""
    from unittest.mock import patch

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True)

    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("fake audio", encoding="utf-8")

    # Pre-create the transcript files that transcribe_to_outputs normally produces
    json_path = out_dir / "transcript.json"
    json_path.write_text(
        json.dumps({"segments": [{"start": 0.0, "end": 1.0, "text": "hello", "speaker": None}]}),
        encoding="utf-8",
    )
    srt_path = out_dir / "transcript.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8")
    txt_path = out_dir / "transcript.txt"
    txt_path.write_text("hello", encoding="utf-8")
    metadata_path = cache_dir / "chunks.json"
    metadata_path.write_text(
        json.dumps({"source_audio": str(audio_path), "duration_sec": 10.0}),
        encoding="utf-8",
    )

    fake_paths = {"json": json_path, "srt": srt_path, "txt": txt_path}
    fake_summary = {
        "chunks": 1,
        "skipped_silent": 0,
        "segments_kept": 1,
        "segments_filtered": 0,
    }

    # Avoid live OpenAI key lookup
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")

    with patch(
        "astrid.packs.editorial.executors.transcribe.run.transcribe_to_outputs",
        return_value=(fake_paths, fake_summary, metadata_path),
    ):
        from astrid.packs.editorial.executors.transcribe.run import main

        ret = main(
            [
                "--audio", str(audio_path),
                "--out", str(out_dir),
            ]
        )
        assert ret == 0

    # Verify transcript files are preserved with original shapes
    assert json_path.is_file()
    transcript_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "segments" in transcript_data
    assert isinstance(transcript_data["segments"], list)
    assert srt_path.is_file()
    assert txt_path.is_file()

    # Verify manifest.json
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file(), f"manifest.json not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "transcript"
    assert manifest["inputs"]["audio"] == str(audio_path)
    assert manifest["inputs"]["model"] == "whisper-1"
    assert manifest["inputs"]["language"] == "en"
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 4
    output_paths = [o["path"] for o in manifest["outputs"]]
    assert any("transcript.json" in p for p in output_paths)
    assert any("transcript.srt" in p for p in output_paths)
    assert any("transcript.txt" in p for p in output_paths)
    assert any("chunks.json" in p for p in output_paths)
    for o in manifest["outputs"]:
        if not o.get("missing"):
            assert "content_hash" in o, f"output missing content_hash: {o['path']}"
            assert "bytes" in o, f"output missing bytes: {o['path']}"
            assert o.get("type") == "file"
    assert isinstance(manifest["warnings"], list)
    assert "created" in manifest


def test_quote_scout_writes_universal_result_manifest(tmp_path: Path) -> None:
    """editorial.quote_scout writes manifest.json with kind=quotes, transcript input, and quote_candidates.json."""
    from unittest.mock import patch

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        json.dumps({"segments": [{"text": "hello", "speaker": "A"}]}),
        encoding="utf-8",
    )

    fake_payload = {
        "version": 1,
        "generated_at": "2025-01-01T00:00:00Z",
        "candidates": [
            {
                "segment_ids": [0],
                "text": "hello",
                "speaker": "A",
                "theme": "intro",
                "power": 4,
                "quote_kind": "hook",
            }
        ],
    }

    with patch(
        "astrid.packs.editorial.executors.quote_scout.run.build_claude_client",
        return_value=object(),
    ), patch(
        "astrid.packs.editorial.executors.quote_scout.run.build_quote_candidates",
        return_value=fake_payload,
    ):
        from astrid.packs.editorial.executors.quote_scout.run import main

        ret = main(
            [
                "--transcript", str(transcript_path),
                "--out", str(out_dir),
            ]
        )
        assert ret == 0

    # Verify quote_candidates.json is preserved with original shape (including version field)
    qc_path = out_dir / "quote_candidates.json"
    assert qc_path.is_file()
    qc_data = json.loads(qc_path.read_text(encoding="utf-8"))
    assert qc_data["version"] == 1
    assert qc_data["generated_at"] == "2025-01-01T00:00:00Z"
    assert "candidates" in qc_data
    assert isinstance(qc_data["candidates"], list)
    assert len(qc_data["candidates"]) == 1
    assert qc_data["candidates"][0]["text"] == "hello"

    # Verify manifest.json
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file(), f"manifest.json not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "quotes"
    assert manifest["inputs"]["transcript"] == str(transcript_path)
    assert manifest["inputs"]["model"] == "claude-sonnet-4-6"
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 1
    assert manifest["outputs"][0]["type"] == "file"
    assert "quote_candidates.json" in manifest["outputs"][0]["path"]
    assert "content_hash" in manifest["outputs"][0]
    assert "bytes" in manifest["outputs"][0]
    assert isinstance(manifest["warnings"], list)
    assert "created" in manifest
