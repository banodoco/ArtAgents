from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.contracts import complete_output_metadata, write_manifest
from astrid.core.executor.registry import load_default_registry


def test_complete_output_metadata_for_file_populates_hash_and_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("hello manifest\n", encoding="utf-8")

    outputs = complete_output_metadata([{"path": "artifact.txt"}], root_dir=tmp_path)

    assert outputs == [
        {
            "path": "artifact.txt",
            "content_hash": "sha256:65e424f78e976256acdf2c33525f3639cbe7b26d103be74bae89011bd71c3d2e",
            "bytes": 15,
            "type": "file",
        }
    ]


def test_complete_output_metadata_for_directory_adds_tree_metadata(tmp_path: Path) -> None:
    out_dir = tmp_path / "bundle"
    out_dir.mkdir()
    (out_dir / "a.txt").write_text("A\n", encoding="utf-8")
    nested = out_dir / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("BB\n", encoding="utf-8")

    outputs = complete_output_metadata([{"path": "bundle"}], root_dir=tmp_path)

    assert outputs[0]["path"] == "bundle"
    assert outputs[0]["type"] == "directory"
    assert outputs[0]["bytes"] == 5
    assert outputs[0]["content_hash"] == "sha256:61bb8156aedb8329ed873ba1fdff79f7182d29536ff09ed83bdd14f5168b2b74"
    assert outputs[0]["entries"] == [
        {
            "path": "a.txt",
            "bytes": 2,
            "content_hash": "sha256:06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0",
        },
        {
            "path": "nested/b.txt",
            "bytes": 3,
            "content_hash": "sha256:68cd080c537d3f1355f357189f74f3fe1c68dd13cf406a84aedc934c90a0df31",
        },
    ]


def test_complete_output_metadata_rejects_missing_required_outputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="required output missing"):
        complete_output_metadata([{"path": "missing.txt"}], root_dir=tmp_path)


def test_complete_output_metadata_allows_missing_optional_outputs(tmp_path: Path) -> None:
    outputs = complete_output_metadata(
        [{"path": "missing.txt", "optional": True, "label": "preview"}],
        root_dir=tmp_path,
    )

    assert outputs == [
        {
            "path": "missing.txt",
            "optional": True,
            "label": "preview",
            "missing": True,
        }
    ]


@pytest.mark.parametrize("kind", ["Image", "image preview", ""])
def test_write_manifest_validates_kind(kind: str, tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("ok\n", encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "kind": kind,
        "inputs": {"prompt": "x"},
        "outputs": [{"path": "artifact.txt"}],
        "created": "2026-06-05T09:39:21Z",
        "warnings": [],
    }

    with pytest.raises(ValueError, match="kind must be a lowercase slug-like string"):
        write_manifest(tmp_path / "manifest.json", manifest)


def test_write_manifest_allows_extra_top_level_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("ok\n", encoding="utf-8")

    manifest = write_manifest(
        tmp_path / "manifest.json",
        {
            "schema_version": 2,
            "kind": "analysis",
            "inputs": {"prompt": "x"},
            "outputs": [{"path": "artifact.txt"}],
            "created": "2026-06-05T09:39:21Z",
            "warnings": [],
            "analysis": {"summary": "kept"},
            "domain_version": 7,
        },
    )

    assert manifest["analysis"] == {"summary": "kept"}
    assert manifest["domain_version"] == 7
    written = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert written["analysis"] == {"summary": "kept"}
    assert written["domain_version"] == 7


def test_complete_output_metadata_preserves_existing_hashes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("hello manifest\n", encoding="utf-8")

    outputs = complete_output_metadata(
        [{"path": "artifact.txt", "content_hash": "sha256:precomputed", "note": "keep"}],
        root_dir=tmp_path,
    )

    assert outputs == [
        {
            "path": "artifact.txt",
            "content_hash": "sha256:precomputed",
            "note": "keep",
            "bytes": 15,
            "type": "file",
        }
    ]


def test_write_manifest_delegates_to_write_json_atomic(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("ok\n", encoding="utf-8")
    manifest_input = {
        "schema_version": 2,
        "kind": "analysis",
        "inputs": {"prompt": "x"},
        "outputs": [{"path": "artifact.txt"}],
        "created": "2026-06-05T09:39:21Z",
        "warnings": [],
    }

    with patch("astrid.contracts.result_manifest.write_json_atomic") as mock_write:
        manifest = write_manifest(tmp_path / "manifest.json", manifest_input)

    mock_write.assert_called_once()
    written_path, written_payload = mock_write.call_args[0]
    assert written_path == tmp_path / "manifest.json"
    assert written_payload == manifest


def test_output_result_registry_conformance_covers_default_registry() -> None:
    registry = load_default_registry()
    registry_ids = {definition.id for definition in registry.list()}

    exemptions_path = Path("astrid/contracts/output_result_exemptions.json")
    payload = json.loads(exemptions_path.read_text(encoding="utf-8"))
    non_exempt_ids = set(payload["non_exempt"])
    exempted_ids = set(payload["exemptions"])

    listed_ids = non_exempt_ids | exempted_ids
    assert non_exempt_ids.isdisjoint(exempted_ids)
    assert registry_ids.issubset(listed_ids)
    assert payload["m1_adopters"] == len(non_exempt_ids)
    assert payload["exempted"] == len(exempted_ids)

    allowed_reasons = {"paid", "GPU", "external-escape-hatch", "no-artifact"}
    for definition in registry.list():
        if definition.id in non_exempt_ids:
            assert definition.metadata.get("output_result_manifest") is True
            continue

        exemption = payload["exemptions"][definition.id]
        assert exemption["reasons"]
        assert set(exemption["reasons"]).issubset(allowed_reasons)
        assert isinstance(exemption["note"], str)
        assert exemption["note"].strip()

    for executor_id in sorted(listed_ids - registry_ids):
        assert payload["exemptions"][executor_id]["reasons"] == ["external-escape-hatch"]


def test_output_result_registry_explicitly_covers_understanding_trio_without_declared_outputs() -> None:
    registry = load_default_registry()
    payload = json.loads(Path("astrid/contracts/output_result_exemptions.json").read_text(encoding="utf-8"))
    non_exempt_ids = set(payload["non_exempt"])

    for executor_id in (
        "understanding.audio_understand",
        "understanding.visual_understand",
        "understanding.video_understand",
    ):
        definition = registry.get(executor_id)
        assert definition.outputs == ()
        assert definition.metadata.get("output_result_manifest") is True
        assert executor_id in non_exempt_ids
