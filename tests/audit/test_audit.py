from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from astrid import audit
from astrid.core.audit import AuditContext


def test_audit_registers_asset_graph_and_report(tmp_path: Path) -> None:
    run = tmp_path / "run"
    artifact = run / "frames" / "frame.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("hello audit", encoding="utf-8")

    ctx = AuditContext.for_run(run)
    source_id = ctx.register_asset(kind="source", path=artifact, label="Source")
    output_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[source_id])
    ctx.register_node(stage="demo", parents=[source_id], outputs=[output_id])

    events = audit.load_ledger(run)
    graph = audit.build_graph(events)
    assert {node["id"] for node in graph["nodes"]} >= {source_id, output_id}
    assert {"from": source_id, "to": output_id} in graph["edges"]

    report = audit.write_report(run)
    assert report == run / "audit" / "report.html"
    html = report.read_text(encoding="utf-8")
    assert "hello audit" in html
    assert "Asset Journey" in html


def test_graph_collapses_duplicate_stable_ids_and_dedupes_edges(tmp_path: Path) -> None:
    run = tmp_path / "run"
    artifact = run / "asset.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("v1", encoding="utf-8")
    ctx = AuditContext.for_run(run)
    parent_id = ctx.register_asset(kind="source", label="Source")
    first_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[parent_id])
    artifact.write_text("v2", encoding="utf-8")
    second_id = ctx.register_asset(kind="text", path=artifact, label="Output", parents=[parent_id])

    graph = audit.build_graph(audit.load_ledger(run))

    assert first_id == second_id
    assert [node["id"] for node in graph["nodes"]].count(first_id) == 1
    assert graph["edges"].count({"from": parent_id, "to": first_id}) == 1
    latest = next(node for node in graph["nodes"] if node["id"] == first_id)
    assert latest["preview"]["text"] == "v2"


def test_audit_redacts_secret_like_values(tmp_path: Path) -> None:
    ctx = AuditContext.for_run(tmp_path / "run")
    ctx.register_node(
        stage="secret-test",
        metadata={"OPENAI_API_KEY": "sk-testsecret1234567890", "nested": {"token": "hf_abcdefghijklmnop"}},
    )
    event = json.loads(ctx.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["metadata"]["OPENAI_API_KEY"] == "<redacted>"
    assert event["metadata"]["nested"]["token"] == "<redacted>"


def test_pipeline_audit_cli_json(tmp_path: Path, capsys) -> None:
    pytest.importorskip("jsonschema")
    # The legacy gateway `audit` verb was retired with the 8-family CLI; the
    # audit CLI now lives at astrid.core.audit.cli.main.
    from astrid.core.audit.cli import main as audit_main

    ctx = AuditContext.for_run(tmp_path / "run")
    asset_id = ctx.register_asset(kind="source", label="Only source")

    assert audit_main(["--run", str(tmp_path / "run"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(node["id"] == asset_id for node in payload["nodes"])


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
    events = [json.loads(line) for line in (out / "audit" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(event.get("registration_source") == "pipeline_fallback" for event in events)


def test_ambient_register_outputs_from_producer(monkeypatch, tmp_path: Path) -> None:
    from astrid.packs.editorial.executors.scenes import run as scenes

    run = tmp_path / "run"
    monkeypatch.setenv("ASTRID_AUDIT_RUN_DIR", str(run))
    json_path = run / "scenes.json"
    csv_path = run / "scenes.csv"

    scenes.write_outputs([{"index": 1, "start": 0.0, "end": 1.0, "duration": 1.0}], json_path, csv_path)

    events = [json.loads(line) for line in (run / "audit" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(event.get("kind") == "scenes" and event.get("path") == "scenes.json" for event in events)
    assert any(event.get("event") == "node.created" and event.get("stage") == "scenes" for event in events)


def test_ambient_register_outputs_inherits_parent_ids(monkeypatch, tmp_path: Path) -> None:
    from astrid.packs.editorial.executors.scenes import run as scenes

    run = tmp_path / "run"
    parent_id = "source-parent"
    monkeypatch.setenv("ASTRID_AUDIT_RUN_DIR", str(run))
    monkeypatch.setenv("ASTRID_AUDIT_PARENT_IDS", parent_id)

    scenes.write_outputs([{"index": 1, "start": 0.0, "end": 1.0, "duration": 1.0}], run / "scenes.json", run / "scenes.csv")

    graph = audit.build_graph(audit.load_ledger(run))
    scenes_node = next(node for node in graph["nodes"] if node.get("kind") == "scenes")
    assert {"from": parent_id, "to": scenes_node["id"]} in graph["edges"]


def test_shots_writes_universal_result_manifest(tmp_path: Path) -> None:
    """editorial.shots writes manifest.json with kind=shots, scenes input, and shots.json."""
    import sys
    from types import SimpleNamespace
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

    # Inject a fake asset_cache module so the ``from ..asset_cache import run``
    # inside main() succeeds.  The import grabs the ``run`` attribute, which
    # needs a ``resolve_input`` callable.
    _fake_ac = SimpleNamespace()
    _fake_ac.resolve_input = staticmethod(lambda video_arg, want: str(video_path))
    _fake_ac.run = _fake_ac  # ``from ..asset_cache import run`` binds this
    sys.modules["astrid.packs.editorial.executors.asset_cache"] = _fake_ac  # type: ignore[assignment]

    try:
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
    finally:
        sys.modules.pop("astrid.packs.editorial.executors.asset_cache", None)

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
    import sys
    from types import SimpleNamespace
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

    # Inject a fake asset_cache module (same pattern as shots test)
    _fake_ac = SimpleNamespace()
    _fake_ac.resolve_input = staticmethod(lambda audio_arg, want: str(audio_path))
    _fake_ac.run = _fake_ac
    sys.modules["astrid.packs.editorial.executors.asset_cache"] = _fake_ac  # type: ignore[assignment]

    # Avoid live OpenAI key lookup
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")

    try:
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
    finally:
        sys.modules.pop("astrid.packs.editorial.executors.asset_cache", None)

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


def test_spatial_audio_page_writes_universal_result_manifest(tmp_path: Path) -> None:
    """reigh.spatial_audio_page writes manifest.json with kind=reigh.spatial_audio_page,
    directory tree output, and preserves HTML-embedded manifest and stdout lines."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    manifest_dir = tmp_path / "manifest_dir"
    manifest_dir.mkdir()

    # Create a minimal tiles.json manifest
    tiles_path = manifest_dir / "tiles.json"
    tiles_path.write_text(
        json.dumps(
            {
                "video": "fake_video.mp4",
                "video_size": [1920, 1080],
                "duration": 30.0,
                "tiles": [
                    {
                        "id": "tile1",
                        "rect_norm": [0.1, 0.1, 0.3, 0.3],
                        "foley_audio": "audio/tile1.wav",
                    },
                    {
                        "id": "tile2",
                        "rect_norm": [0.6, 0.6, 0.3, 0.3],
                        "foley_audio": "audio/tile2.wav",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    from astrid.packs.reigh.executors.spatial_audio_page.run import main

    ret = main(
        [
            "--manifest",
            str(tiles_path),
            "--out",
            str(out_dir),
            "--no-copy-assets",
        ]
    )
    assert ret == 0

    # Verify index.html exists with HTML-embedded manifest preserved
    index_html = out_dir / "index.html"
    assert index_html.is_file(), "index.html not found in output directory"
    html_content = index_html.read_text(encoding="utf-8")
    assert '<script id="manifest" type="application/json">' in html_content, (
        "HTML-embedded manifest not preserved"
    )

    # Verify manifest.json
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file(), f"manifest.json not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "reigh.spatial_audio_page"
    assert manifest["inputs"]["manifest"] == str(tiles_path)
    assert isinstance(manifest["outputs"], list)
    assert len(manifest["outputs"]) == 1
    assert manifest["outputs"][0]["type"] == "directory"
    assert manifest["outputs"][0]["tree"] is True
    assert "entries" in manifest["outputs"][0], "directory tree entries missing"
    assert isinstance(manifest["outputs"][0]["entries"], list)
    assert len(manifest["outputs"][0]["entries"]) >= 1, (
        "expected at least index.html in directory tree"
    )
    # At least index.html should be in the tree
    entry_paths = [e["path"] for e in manifest["outputs"][0]["entries"]]
    assert "index.html" in entry_paths, "index.html not in directory tree entries"
    assert "content_hash" in manifest["outputs"][0]
    assert manifest["outputs"][0]["content_hash"].startswith("sha256:")
    assert "bytes" in manifest["outputs"][0]
    assert manifest["outputs"][0]["bytes"] > 0
    assert isinstance(manifest["warnings"], list)
    assert "created" in manifest

    # Tree-hash/bytes stability: same outputs → deterministic tree hash.
    # write_manifest computes the tree hash *before* writing manifest.json,
    # so the tree only includes index.html at that point.  Remove manifest.json
    # to reproduce the same state for a stability recomputation.
    from astrid.core._shared.result_manifest import complete_output_metadata

    tree_hash_1 = manifest["outputs"][0]["content_hash"]
    tree_bytes_1 = manifest["outputs"][0]["bytes"]
    manifest_path.unlink()

    recomputed = complete_output_metadata(
        [{"path": str(out_dir), "type": "directory", "tree": True}],
        root_dir=out_dir,
    )
    assert recomputed[0]["content_hash"] == tree_hash_1, (
        "tree hash is not stable across recomputation"
    )
    assert recomputed[0]["bytes"] == tree_bytes_1, (
        "tree bytes are not stable across recomputation"
    )
