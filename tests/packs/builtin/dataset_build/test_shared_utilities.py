from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from astrid.packs.builtin.dataset_build.config import MISSING_SCHEMA_VERSION_SOURCE
from astrid.packs.builtin.dataset_build.artifacts import (
    load_valid_cached_sidecar,
    prompt_hash,
    schema_hash,
    sidecar_hashes,
    write_hashed_sidecar,
)
from astrid.packs.builtin.dataset_build.items import (
    config_hash,
    deterministic_id,
    explicit_rights,
    make_candidate_item,
    make_review_item,
    repo_relative_path,
    sha256_file,
)
from astrid.packs.builtin.dataset_build.media import extract_clip_ffmpeg, ffprobe_metadata
from astrid.packs.builtin.dataset_build.state import (
    make_initial_state,
    read_review_state,
    set_status,
    write_review_state,
)


ROOT = Path(__file__).resolve().parents[4]
SCHEMAS = ROOT / "astrid" / "packs" / "builtin" / "dataset_build" / "schemas"


def _schema_registry() -> Registry:
    registry = Registry()
    for path in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(path.name, Resource.from_contents(schema))
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def _validate(schema_name: str, payload: dict[str, Any]) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema, registry=_schema_registry()).validate(payload)


def test_hashes_ids_and_repo_relative_paths_are_stable(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"dataset")

    assert sha256_file(payload) == "b277fd623676a525c29b9eb155afc8c9010681814ceafb2d7627f47b9a232576"
    assert config_hash({"b": 2, "a": 1}) == config_hash({"a": 1, "b": 2})
    assert deterministic_id("source", 1, prefix="clip") == deterministic_id("source", 1, prefix="clip")
    assert repo_relative_path(ROOT / "runs" / "x.mp4") == "runs/x.mp4"
    assert repo_relative_path(tmp_path / "outside.mp4").endswith("outside.mp4")


def test_artifact_sidecar_hash_helpers_validate_production_cache_hits(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"clip")
    schema = tmp_path / "caption.schema.json"
    schema.write_text('{"type":"object"}', encoding="utf-8")
    hashes = sidecar_hashes(
        prompt="Describe this.",
        schema=schema,
        media=media,
        config={"model": "gpt-test", "budget_tracker": object()},
    )
    sidecar = tmp_path / "clip.caption.json"

    written = write_hashed_sidecar(sidecar, {"text": "Caption.", "schema_version": 1}, hashes)

    assert written["hashes"]["prompt_hash"] == prompt_hash("Describe this.")
    assert written["hashes"]["schema_hash"] == schema_hash(schema)
    assert load_valid_cached_sidecar(sidecar, hashes)["text"] == "Caption."
    changed = dict(hashes)
    changed["prompt_hash"] = prompt_hash("Changed prompt.")
    assert load_valid_cached_sidecar(sidecar, changed) is None


def test_raw_sidecars_are_fixture_only_cache_hits(tmp_path: Path) -> None:
    sidecar = tmp_path / "raw.caption.json"
    sidecar.write_text(json.dumps({"text": "Fixture caption."}), encoding="utf-8")
    hashes = {"prompt_hash": "p", "media_hash": "m"}

    assert load_valid_cached_sidecar(sidecar, hashes) is None
    assert load_valid_cached_sidecar(sidecar, hashes, fixture_mode=True) == {"text": "Fixture caption."}


def test_candidate_and_review_items_include_explicit_rights_and_validate(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"clip-bytes")

    candidate = make_candidate_item(
        source_type="local_folder",
        source_id="clip-001",
        source_url=media.as_uri(),
        media_path=media,
        duration_s=3.5,
        source_metadata={"title": "Fixture"},
        acquired_at="2026-05-21T00:00:00Z",
    )
    assert candidate["rights"]["rights_status"] == "unknown"
    assert candidate["rights"]["license"] == "unknown"
    _validate("candidate-item.schema.json", candidate)

    review_item = make_review_item(
        candidate,
        item_id="item-001",
        bucket="smoke",
        caption={"text": "A short clip.", "schema_version": 1, "confidence": 0.8, "model": "fixture"},
    )
    assert review_item["review_status"] == "pending"
    assert review_item["rights"]["rights_status"] == "unknown"
    _validate("review-item.schema.json", review_item)


def test_explicit_rights_preserves_status_and_defaults_missing_fields() -> None:
    rights = explicit_rights({"rights_status": "verified", "license": "CC0"})
    assert rights == {
        "license": "CC0",
        "attribution": "",
        "restrictions": [],
        "rights_status": "verified",
    }


def test_ffprobe_metadata_parses_video_stream() -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30000/1001",
                        "duration": "12.5",
                    }
                ],
                "format": {"duration": "12.5", "size": "42"},
            }
        )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    metadata = ffprobe_metadata("clip.mp4", runner=runner)

    assert calls[0][0] == "ffprobe"
    assert metadata["duration_s"] == 12.5
    assert metadata["resolution"] == {"width": 1920, "height": 1080}
    assert round(metadata["fps"], 3) == 29.97
    assert metadata["codec"] == "h264"
    assert metadata["file_size_bytes"] == 42


def test_extract_clip_ffmpeg_builds_internal_clip_command(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    out = extract_clip_ffmpeg("source.mp4", start_s=1.25, end_s=4.75, out_path=tmp_path / "clip.mp4", runner=runner)

    cmd = calls[0]
    assert out == tmp_path / "clip.mp4"
    assert cmd[:5] == ["ffmpeg", "-y", "-ss", "1.250", "-i"]
    assert cmd[cmd.index("-t") + 1] == "3.500"
    assert str(out) == cmd[-1]


def test_review_state_lifecycle_writes_schema_valid_versions(tmp_path: Path) -> None:
    state = make_initial_state(
        run_id="run-001",
        writer_id="agent-001",
        config_hash="abc123",
        buckets={"smoke": 2},
        schema_version_source=MISSING_SCHEMA_VERSION_SOURCE,
        now="2026-05-21T00:00:00Z",
    )
    _validate("run-state.schema.json", state)

    path = tmp_path / "review_state.json"
    written = write_review_state(path, state, now="2026-05-21T00:00:01Z")
    assert written["state_version"] == 1
    assert written["updated_at"] == "2026-05-21T00:00:01Z"
    _validate("run-state.schema.json", read_review_state(path))

    preview_ready = set_status(path, "preview_ready", now="2026-05-21T00:00:02Z")
    assert preview_ready["state_version"] == 2
    assert preview_ready["status"] == "preview_ready"
    _validate("run-state.schema.json", read_review_state(path))

    finalized = set_status(path, "finalized", now="2026-05-21T00:00:03Z")
    assert finalized["state_version"] == 3
    assert finalized["status"] == "finalized"
    assert finalized["completed_at"] == "2026-05-21T00:00:03Z"
    _validate("run-state.schema.json", read_review_state(path))
