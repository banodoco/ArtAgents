from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core._shared.result_manifest import (
    ResultManifestError,
    ValidatedResultManifest,
    build_manifest,
    complete_output_metadata,
    read_result_manifest,
    validate_result_manifest,
    write_manifest,
)
from astrid.core.contracts.errors import AstridError
from astrid.core.execution.executor.registry import load_default_registry


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
    with pytest.raises(AstridError, match="required output missing"):
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

    with patch("astrid.core._shared.result_manifest.write_json_atomic") as mock_write:
        manifest = write_manifest(tmp_path / "manifest.json", manifest_input)

    mock_write.assert_called_once()
    written_path, written_payload = mock_write.call_args[0]
    assert written_path == tmp_path / "manifest.json"
    assert written_payload == manifest


# -- build_manifest -------------------------------------------------------


def test_build_manifest_constructs_minimal_dict() -> None:
    manifest = build_manifest(
        kind="analysis",
        inputs={"prompt": "hello"},
        outputs=[{"path": "out.txt"}],
        created="2026-06-05T09:39:21Z",
    )

    assert manifest == {
        "schema_version": 1,
        "kind": "analysis",
        "inputs": {"prompt": "hello"},
        "outputs": [{"path": "out.txt"}],
        "created": "2026-06-05T09:39:21Z",
        "warnings": [],
    }


def test_build_manifest_defaults_warnings_to_empty_list() -> None:
    manifest = build_manifest(kind="test", inputs={}, outputs=[], created="t")

    assert manifest["warnings"] == []


def test_build_manifest_preserves_explicit_warnings() -> None:
    manifest = build_manifest(
        kind="test",
        inputs={},
        outputs=[],
        created="t",
        warnings=["low disk space"],
    )

    assert manifest["warnings"] == ["low disk space"]


def test_build_manifest_respects_custom_schema_version() -> None:
    manifest = build_manifest(
        kind="test",
        inputs={},
        outputs=[],
        created="t",
        schema_version=3,
    )

    assert manifest["schema_version"] == 3


def test_build_manifest_passthrough_extras() -> None:
    manifest = build_manifest(
        kind="analysis",
        inputs={"prompt": "x"},
        outputs=[{"path": "artifact.txt"}],
        created="2026-06-05T09:39:21Z",
        analysis={"summary": "kept"},
        domain_version=7,
    )

    assert manifest["analysis"] == {"summary": "kept"}
    assert manifest["domain_version"] == 7
    assert manifest["kind"] == "analysis"
    assert manifest["schema_version"] == 1


def test_build_manifest_result_passes_write_manifest_validation(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("ok\n", encoding="utf-8")

    manifest = build_manifest(
        kind="analysis",
        inputs={"prompt": "x"},
        outputs=[{"path": "artifact.txt"}],
        created="2026-06-05T09:39:21Z",
        extra_tag="passthrough",
    )

    result = write_manifest(tmp_path / "manifest.json", manifest)

    assert result["extra_tag"] == "passthrough"
    assert result["kind"] == "analysis"


def test_build_manifest_copies_inputs_and_outputs() -> None:
    inputs = {"key": "value"}
    outputs = [{"path": "f"}]

    manifest = build_manifest(kind="test", inputs=inputs, outputs=outputs, created="t")

    inputs["extra"] = "leaked"
    outputs[0]["path"] = "leaked"
    outputs.append({"path": "also-leaked"})

    assert "extra" not in manifest["inputs"]
    assert manifest["outputs"] == [{"path": "f"}]


# -- registry conformance -------------------------------------------------


def test_output_result_registry_conformance_covers_default_registry() -> None:
    registry = load_default_registry()
    registry_ids = {definition.id for definition in registry.list()}

    exemptions_path = Path("astrid/core/contracts/output_result_exemptions.json")
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


def test_output_result_registry_explicitly_covers_understanding_trio() -> None:
    registry = load_default_registry()
    payload = json.loads(Path("astrid/core/contracts/output_result_exemptions.json").read_text(encoding="utf-8"))
    non_exempt_ids = set(payload["non_exempt"])

    # Audio now declares the two concrete files its runtime receives through
    # placeholders.  Visual/video retain their manifest-only contract because
    # their runtimes choose their result path dynamically.
    audio = registry.get("understanding.audio_understand")
    assert tuple(output.name for output in audio.outputs) == ("analysis", "manifest")
    assert audio.metadata.get("output_result_manifest") is True
    assert "understanding.audio_understand" in non_exempt_ids

    for executor_id in (
        "understanding.visual_understand",
        "understanding.video_understand",
    ):
        definition = registry.get(executor_id)
        assert definition.outputs == ()
        assert definition.metadata.get("output_result_manifest") is True
        assert executor_id in non_exempt_ids


# ---------------------------------------------------------------------------
# m2 plan step 9: strict result-manifest read/validate helpers
# ---------------------------------------------------------------------------


def _digest(data: bytes) -> str:
    """Return the ``sha256:<hex>`` content hash of *data* (byte identity)."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _base_manifest(staging: Path, outputs: list[dict]) -> dict:
    """A minimal universal result manifest mapping for strict validation."""
    return {
        "schema_version": 1,
        "kind": "analysis",
        "inputs": {"prompt": "hello"},
        "outputs": outputs,
        "created": "2026-08-16T12:00:00Z",
        "warnings": [],
    }


def _write_file(staging: Path, rel: str, data: bytes) -> dict:
    """Write *data* under staging and return a validated output descriptor."""
    path = staging / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "path": rel,
        "content_hash": _digest(data),
        "bytes": len(data),
        "type": "file",
    }


def test_validate_result_manifest_accepts_concrete_contained_files(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    first = _write_file(staging, "out.png", b"\x89PNG fake bytes")
    second = _write_file(staging, "logs/run.txt", b"done\n")
    manifest = _base_manifest(
        staging,
        [
            {**first, "ordinal": 0, "role": "result", "is_primary": True},
            {**second, "ordinal": 1, "role": "log"},
        ],
    )

    validated = validate_result_manifest(manifest, staging_root=staging)

    assert isinstance(validated, ValidatedResultManifest)
    assert validated.kind == "analysis"
    assert validated.schema_version == 1
    assert validated.inputs == {"prompt": "hello"}
    assert [output.path for output in validated.outputs] == [
        "out.png",
        "logs/run.txt",
    ]
    assert [output.ordinal for output in validated.outputs] == [0, 1]
    assert [output.is_primary for output in validated.outputs] == [True, False]
    assert validated.outputs[0].content_hash == first["content_hash"]
    assert validated.outputs[0].bytes == len(b"\x89PNG fake bytes")
    assert validated.primary_output is validated.outputs[0]
    assert validated.primary_output is not None and validated.primary_output.path == "out.png"


def test_validate_result_manifest_ordinal_falls_back_to_position(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    first = _write_file(staging, "a.txt", b"a")
    second = _write_file(staging, "b.txt", b"bb")

    validated = validate_result_manifest(
        _base_manifest(staging, [first, second]),
        staging_root=staging,
    )

    assert [output.ordinal for output in validated.outputs] == [0, 1]


def test_validate_result_manifest_rejects_missing_file(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    manifest = _base_manifest(
        staging,
        [{"path": "missing.txt", "content_hash": _digest(b"x")}],
    )

    with pytest.raises(ResultManifestError, match="missing"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_optional_missing_file(tmp_path: Path) -> None:
    """The optional flag never excuses a missing concrete output: the strict
    executor contract requires every declared output to be present."""
    staging = tmp_path / "staging"
    staging.mkdir()
    manifest = _base_manifest(
        staging,
        [
            {
                "path": "optional.txt",
                "optional": True,
                "content_hash": _digest(b"x"),
            }
        ],
    )

    with pytest.raises(ResultManifestError, match="missing"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_parent_traversal(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    # The escaped file exists outside staging: containment must reject it
    # even though the bytes are present and hashable.
    outside = tmp_path / "escape.txt"
    outside.write_bytes(b"secret")
    manifest = _base_manifest(
        staging,
        [
            {
                "path": "../escape.txt",
                "content_hash": _digest(b"secret"),
            }
        ],
    )

    with pytest.raises(ResultManifestError, match="escapes the assigned staging"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_absolute_path(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    absolute = tmp_path / "absolute.txt"
    absolute.write_bytes(b"x")
    manifest = _base_manifest(
        staging,
        [{"path": str(absolute), "content_hash": _digest(b"x")}],
    )

    with pytest.raises(ResultManifestError, match="escapes the assigned staging"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_hash_mismatch(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "out.txt", b"actual bytes")
    manifest = _base_manifest(
        staging,
        [{"path": "out.txt", "content_hash": _digest(b"different bytes")}],
    )

    with pytest.raises(ResultManifestError, match="hashes to"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_missing_content_hash(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "out.txt", b"actual bytes")
    manifest = _base_manifest(staging, [{"path": "out.txt"}])

    with pytest.raises(ResultManifestError, match="must declare content_hash"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_directory_identity(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "bundle").mkdir()
    manifest = _base_manifest(
        staging,
        [{"path": "bundle", "content_hash": _digest(b"x")}],
    )

    with pytest.raises(ResultManifestError, match="directory"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_declared_directory_type(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "out.txt", b"x")
    manifest = _base_manifest(
        staging,
        [
            {
                "path": "out.txt",
                "type": "directory",
                "content_hash": _digest(b"x"),
            }
        ],
    )

    with pytest.raises(ResultManifestError, match="directory"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_duplicate_ordinals(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    first = _write_file(staging, "a.txt", b"a")
    second = _write_file(staging, "b.txt", b"bb")
    manifest = _base_manifest(
        staging,
        [{**first, "ordinal": 7}, {**second, "ordinal": 7}],
    )

    with pytest.raises(ResultManifestError, match="duplicate output ordinal 7"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_multiple_primary_outputs(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    first = _write_file(staging, "a.txt", b"a")
    second = _write_file(staging, "b.txt", b"bb")
    manifest = _base_manifest(
        staging,
        [
            {**first, "role": "result", "is_primary": True},
            {**second, "role": "result", "is_primary": True},
        ],
    )

    with pytest.raises(ResultManifestError, match="more than one primary"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_non_result_role_primary(tmp_path: Path) -> None:
    """Mirrors the frozen task_outputs CHECK (role = 'result' OR is_primary = 0)."""
    staging = tmp_path / "staging"
    staging.mkdir()
    first = _write_file(staging, "a.txt", b"a")
    manifest = _base_manifest(
        staging,
        [{**first, "role": "preview", "is_primary": True}],
    )

    with pytest.raises(ResultManifestError, match="cannot be primary"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_symlink_escaping_staging(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    (staging / "link.txt").symlink_to(outside)
    manifest = _base_manifest(
        staging,
        [{"path": "link.txt", "content_hash": _digest(b"secret")}],
    )

    with pytest.raises(ResultManifestError, match="escapes the assigned staging"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_accepts_symlink_inside_staging(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "real.txt", b"data")
    (staging / "alias.txt").symlink_to(staging / "real.txt")
    manifest = _base_manifest(
        staging,
        [{"path": "alias.txt", "content_hash": _digest(b"data")}],
    )

    validated = validate_result_manifest(manifest, staging_root=staging)

    assert validated.outputs[0].path == "alias.txt"
    assert validated.outputs[0].content_hash == _digest(b"data")


def test_validate_result_manifest_rejects_broken_symlink(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "dangling.txt").symlink_to(staging / "does-not-exist.txt")
    manifest = _base_manifest(
        staging,
        [{"path": "dangling.txt", "content_hash": _digest(b"x")}],
    )

    with pytest.raises(ResultManifestError, match="missing"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_nonexistent_staging_root(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    manifest = _base_manifest(staging, [{"path": "x.txt", "content_hash": _digest(b"x")}])

    with pytest.raises(ResultManifestError, match="existing directory"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_rejects_malformed_manifest(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "out.txt", b"x")

    missing_field = _base_manifest(staging, [{"path": "out.txt"}])
    del missing_field["kind"]
    with pytest.raises(ResultManifestError, match="missing required fields"):
        validate_result_manifest(missing_field, staging_root=staging)

    bad_kind = _base_manifest(staging, [{"path": "out.txt"}])
    bad_kind["kind"] = "Not A Kind"
    with pytest.raises(ResultManifestError, match="kind must be a lowercase"):
        validate_result_manifest(bad_kind, staging_root=staging)

    empty_outputs = _base_manifest(staging, [])
    with pytest.raises(ResultManifestError, match="non-empty list"):
        validate_result_manifest(empty_outputs, staging_root=staging)


def test_validate_result_manifest_rejects_wrong_declared_bytes(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    _write_file(staging, "out.txt", b"12345")
    manifest = _base_manifest(
        staging,
        [{"path": "out.txt", "content_hash": _digest(b"12345"), "bytes": 99}],
    )

    with pytest.raises(ResultManifestError, match="declares bytes 99"):
        validate_result_manifest(manifest, staging_root=staging)


def test_validate_result_manifest_accepts_nested_contained_paths(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    nested = _write_file(staging, "artifacts/deep/out.png", b"\x89PNG")
    manifest = _base_manifest(
        staging,
        [{**nested, "is_primary": True, "role": "result"}],
    )

    validated = validate_result_manifest(manifest, staging_root=staging)

    assert validated.outputs[0].path == "artifacts/deep/out.png"
    assert validated.to_dict()["outputs"][0]["path"] == "artifacts/deep/out.png"


def test_read_result_manifest_reads_and_validates_file(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    output = _write_file(staging, "out.txt", b"payload")
    manifest_path = staging / "manifest.json"
    manifest_path.write_text(
        json.dumps(_base_manifest(staging, [output])),
        encoding="utf-8",
    )

    validated = read_result_manifest(manifest_path, staging_root=staging)

    assert validated.kind == "analysis"
    assert validated.outputs[0].path == "out.txt"
    assert validated.outputs[0].content_hash == output["content_hash"]


def test_read_result_manifest_rejects_unreadable_file(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    missing = staging / "no-manifest.json"

    with pytest.raises(ResultManifestError, match="cannot read result manifest"):
        read_result_manifest(missing, staging_root=staging)
