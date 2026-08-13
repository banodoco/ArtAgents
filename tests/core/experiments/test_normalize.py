"""Tests for provider-independent manifest normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.experiments.normalize import (
    _provider_from_kind,
    _verify_artifact,
    build_diagnostics,
    build_normalized_review,
    normalize_case_from_manifest,
)
from astrid.core.experiments.schema import (
    validate_diagnostics,
    validate_review,
)

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "experiments" / "manifests"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# ── Provider derivation ────────────────────────────────────────────────────

class TestProviderDerivation:
    def test_fal_explicit_from_kind(self):
        assert _provider_from_kind("generation.generate_image_fal") == "fal"

    def test_fal_from_generation_kind_fal(self):
        assert _provider_from_kind("generation.generate_video_fal") == "fal"

    def test_openai_from_kind(self):
        assert _provider_from_kind("generation.generate_image_openai") == "openai"

    def test_comfyui_from_kind(self):
        assert _provider_from_kind("vibecomfy.run") == "comfyui"

    def test_local_from_kind(self):
        assert _provider_from_kind("local.generate") == "local"

    def test_local_from_execution(self):
        assert _provider_from_kind("generation.generate_image", execution="local") == "local"

    def test_discord_from_kind(self):
        assert _provider_from_kind("discord_browser.generate") == "discord_browser"

    def test_unknown_default(self):
        assert _provider_from_kind("something.else") == "unknown"

    def test_generic_generation_is_not_fal(self):
        """Generic generation.generate_image without 'fal' in kind → unknown."""
        assert _provider_from_kind("generation.generate_image") == "unknown"
        assert _provider_from_kind("generation.generate_video") == "unknown"


# ── Source URL elimination ──────────────────────────────────────────────────

class TestSourceURLElimination:
    def test_source_urls_become_counts_not_strings(self, tmp_path):
        """source_urls in manifest → source_url_count / source_urls_present, no URL strings."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [],
            "source_urls": [
                "https://storage.googleapis.com/bucket/output.png?Expires=999999&Signature=signed&Key-Pair-Id=APKAI",
                "https://user:token@cdn.example.com/file.mp4",
                "https://example.com/path/with/secret-token-abc123",
            ],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "url-free-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "URL Free",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        # No URL strings anywhere
        serialized = json.dumps(result, sort_keys=True)
        assert "_diagnostic_source_urls" not in result
        assert "source_url_count" in result
        assert result["source_url_count"] == 3
        assert result["source_urls_present"] is True
        # Ensure no URL substrings leak through
        assert "https://" not in serialized
        assert "storage.googleapis.com" not in serialized
        assert "cdn.example.com" not in serialized

    def test_no_source_urls_omits_fields(self, tmp_path):
        """When no source_urls, source_url_count and source_urls_present are absent."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "no-urls-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "No URLs",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        assert "source_url_count" not in result
        assert "source_urls_present" not in result

    def test_secrets_in_path_query_fragment_never_survive(self, tmp_path):
        """Secrets in path segments, query, fragment are never in serialized output."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        secret_api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [],
            "source_urls": [
                f"https://api.example.com/v1/{secret_api_key}/download?token={secret_api_key}#{secret_api_key}",
                f"https://user:{secret_api_key}@cdn.example.com/signed/{secret_api_key}",
            ],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "secret-free-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "Secret Free",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        serialized = json.dumps(result, sort_keys=True)
        assert secret_api_key not in serialized
        assert "api.example.com" not in serialized
        assert "cdn.example.com" not in serialized
        # Only count/presence evidence, no URL strings
        assert result.get("source_url_count") == 2
        assert result.get("source_urls_present") is True


# ── V2 manifest normalization (Fal success) ────────────────────────────────

class TestFalSuccessV2:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("fal_success_t2i.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "fal-t2i-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "Fal T2I",
            "factors": {"method": "fal"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_status(self, manifest, case, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # Create the actual output file so local verification passes
        (run_dir / "images").mkdir(parents=True)
        (run_dir / "images" / "0-flux-dev.png").write_bytes(b"fake png content for verification")
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["case_id"] == "fal-t2i-1"
        assert result["status"] == "completed"
        assert result["provider"] == "fal"
        assert result["model"] == "flux-dev"
        assert result["model_actual"] == "fal-ai/flux/dev"
        assert result["mode"] == "t2i"
        assert result["prompt"] == "a serene mountain lake at dawn with mist rising from the water"
        assert result["parameters"]["seed"] == 42
        assert result["parameters"]["size"] == "1024x1024"
        assert result["cost_usd"] == 0.002
        assert result["timing"]["duration_ms"] == 3421
        assert len(result["outputs"]) == 1
        assert result["outputs"][0]["path"] == "images/0-flux-dev.png"
        # Verified: file exists, local hash computed.  Reported hash in manifest
        # differs from local, so content_hash = local, reported_content_hash = manifest value
        assert result["outputs"][0]["verified"] is True
        assert "content_hash" in result["outputs"][0]
        assert result["outputs"][0]["content_hash"].startswith("sha256:")
        assert result["outputs"][0]["reported_content_hash"] == "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_deterministic_normalization(self, manifest, case, tmp_path):
        """Same input produces identical output."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "images").mkdir(parents=True)
        (run_dir / "images" / "0-flux-dev.png").write_bytes(b"fake png content for verification")
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result1 = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        result2 = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        assert result1 == result2


# ── Fal failure normalization ──────────────────────────────────────────────

class TestFalFailure:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("fal_failure_policy_reject.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "fal-fail-1",
            "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
            "label": "Fal Failure",
            "factors": {"method": "fal"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_failure(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["status"] == "failed"
        assert "Fal API returned 400" in str(result["error"])
        assert result["outputs"] == []
        assert "dropped_features" in result


# ── OpenAI normalization ───────────────────────────────────────────────────

class TestOpenAISuccess:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("openai_success_t2i.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "openai-t2i-1",
            "run_id": "2EFGHJKMNPQRSTVWXYZabcdefg",
            "label": "OpenAI T2I",
            "factors": {"method": "openai"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_openai(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-image-2"
        assert result["status"] == "completed"
        assert result["cost_usd"] == 0.04


class TestOpenAIImageRef:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("openai_success_i2i_ref.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "openai-i2i-1",
            "run_id": "3NPQRSTVWXYZabcdefghjkmnpq",
            "label": "OpenAI I2I",
            "factors": {"method": "openai"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_extracts_image_reference_input(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["mode"] == "edit"
        inputs = result["inputs"]
        assert len(inputs) == 1
        assert inputs[0]["role"] == "appearance_reference"
        assert inputs[0]["path"] == "inputs/desert-plant.png"


# ── Local generation normalization ─────────────────────────────────────────

class TestLocalGeneration:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("local_success_t2i.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "local-1",
            "run_id": "4WXYZabcdefghjkmnpqrstvwxy",
            "label": "Local T2I",
            "factors": {"method": "local"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_local(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["provider"] == "local"
        assert result["status"] == "completed"


# ── ComfyUI normalization ─────────────────────────────────────────────────

class TestComfyUISuccess:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("comfyui_success.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "comfy-1",
            "run_id": "5defghjkmnpqrstvwxyz012345",
            "label": "ComfyUI",
            "factors": {"method": "comfyui"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_comfyui_v1(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "output.mp4").write_bytes(b"fake mp4 content for verification")
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["provider"] == "comfyui"
        assert result["status"] == "completed"
        # v1 manifest: prompt is not in request, but inputs.prompt
        assert result["prompt"] == "A desert plant growing in time-lapse, cinematic lighting"
        assert len(result["outputs"]) == 1
        assert "output.mp4" in result["outputs"][0]["path"]
        assert result["outputs"][0]["verified"] is True


# ── Discord normalization ──────────────────────────────────────────────────

class TestDiscordSuccess:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("discord_success.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "discord-ok-1",
            "run_id": "6mnpqrstvwxyz0123456789ABC",
            "label": "Discord OK",
            "factors": {"method": "discord"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_discord_success(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["provider"] == "discord_browser"
        assert result["status"] == "completed"


class TestDiscordRejection:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("discord_rejection.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "discord-rej-1",
            "run_id": "7vwxyz0123456789ABCDEFGHJK",
            "label": "Discord Rejection",
            "factors": {"method": "discord"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_rejection(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["status"] == "provider_rejected"
        assert "not allowed" in str(result["error"])
        assert result["outputs"] == []


class TestDiscordTimeout:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("discord_timeout.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "discord-to-1",
            "run_id": "023456789ABCDEFGHJKMNPQRST",
            "label": "Discord Timeout",
            "factors": {"method": "discord"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_timeout(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["status"] == "timed_out"
        assert "timed out" in str(result["error"]).lower()


class TestDiscordInterrupted:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("discord_interrupted.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "discord-int-1",
            "run_id": "19ABCDEFGHJKMNPQRSTVWXYZab",
            "label": "Discord Interrupted",
            "factors": {"method": "discord"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_interrupted(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["status"] == "interrupted"


class TestDiscordPartial:
    @pytest.fixture
    def manifest(self):
        return _load_fixture("discord_partial.json")

    @pytest.fixture
    def case(self):
        return {
            "case_id": "discord-part-1",
            "run_id": "2FGHJKMNPQRSTVWXYZabcdefgh",
            "label": "Discord Partial",
            "factors": {"method": "discord"},
            "relationship": {"type": "baseline", "case_id": None},
        }

    def test_normalizes_partial(self, manifest, case, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        assert result["status"] == "partial"
        assert len(result["outputs"]) == 1  # partial output still present


# ── Input echo detection ───────────────────────────────────────────────────

class TestInputEcho:
    def test_detects_input_output_hash_equality(self, tmp_path):
        """When an output hash matches an input hash, flag as input echo."""
        # Use identical content for both files so local hashes match
        identical_content = b"identical content for echo detection"

        manifest = {
            "schema_version": 1,
            "kind": "discord_browser.generate",
            "inputs": {
                "prompt": "test",
                "video": "inputs/ref.mp4",
                "video_sha256": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
            },
            "outputs": [
                {
                    "path": "outputs/result.mp4",
                    "content_hash": "sha256:a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
                    "bytes": 100,
                }
            ],
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
        }
        case = {
            "case_id": "echo-1",
            "run_id": "3NPQRSTVWXYZabcdefghjkmnpq",
            "label": "Echo",
            "factors": {"method": "test"},
            "relationship": {"type": "baseline", "case_id": None},
        }

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "inputs").mkdir(parents=True)
        (run_dir / "outputs").mkdir(parents=True)
        # Create identical content files so local SHA-256 hashes match
        (run_dir / "inputs" / "ref.mp4").write_bytes(identical_content)
        (run_dir / "outputs" / "result.mp4").write_bytes(identical_content)
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        gaps = result["capture_gaps"]
        echo_gaps = [g for g in gaps if "input echo" in str(g.get("detail", "")).lower()]
        assert len(echo_gaps) > 0, f"Expected input echo gap, got: {gaps}"


# ── Capture gap detection ──────────────────────────────────────────────────

class TestCaptureGaps:
    def test_missing_prompt_gap(self, tmp_path):
        """Manifest with no prompt generates missing_prompt gap."""
        manifest = {
            "schema_version": 1,
            "kind": "unknown.run",
            "inputs": {},
            "outputs": [],
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
        }
        case = {
            "case_id": "gap-1",
            "run_id": "4VWXYZabcdefghjkmnpqrstvwx",
            "label": "No prompt",
            "factors": {"method": "test"},
            "relationship": {"type": "baseline", "case_id": None},
        }

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        gaps = result["capture_gaps"]
        gap_kinds = {g["kind"] for g in gaps}
        assert "missing_prompt" in gap_kinds

    def test_missing_output_hash_gap(self, tmp_path):
        """Output without content_hash must record a capture gap, not fabricate."""
        manifest = {
            "schema_version": 1,
            "kind": "unknown.run",
            "inputs": {"prompt": "test"},
            "outputs": [{"path": "outputs/img.png"}],
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
        }
        case = {
            "case_id": "nohash-1",
            "run_id": "5WXYZabcdefghjkmnpqrstvwxy",
            "label": "No hash",
            "factors": {"method": "test"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(manifest))

        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )

        output = result["outputs"][0]
        # Must NOT contain a fabricated 64-zero hash
        if "content_hash" in output:
            assert output["content_hash"] != "sha256:" + "0" * 64

        gap_kinds = {g["kind"] for g in result["capture_gaps"]}
        assert "missing_output_hash" in gap_kinds


# ── Bulk normalization (build_normalized_review) ───────────────────────────

class TestBuildNormalizedReview:
    def test_builds_from_multiple_manifests(self, tmp_path):
        experiment = {
            "schema_version": 1,
            "experiment_id": "multi-test",
            "project_slug": "test",
            "title": "Multi Test",
            "question": "Q?",
            "hypotheses": [],
            "factors": [{"id": "method", "values": ["a", "b"]}],
            "rubric": [{"id": "q", "label": "Q", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"method": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                },
                {
                    "case_id": "c2",
                    "label": "C2",
                    "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                    "factors": {"method": "b"},
                    "relationship": {"type": "variant", "case_id": "c1"},
                },
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        # Create two run directories with manifests
        m1 = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test A", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        m2 = {
            "schema_version": 2,
            "kind": "generation.generate_image_openai",
            "modality": "image",
            "model": "gpt-image-2",
            "mode_used": "t2i",
            "model_actual": "gpt-image-2",
            "execution": "cloud",
            "request": {"prompt": "test B", "seed": 2, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "b" * 64}],
            "seed": 2,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }

        runs_dir = tmp_path / "runs"
        for run_id, m in [("00123456789ABCDEFGHJKMNPQR", m1), ("1789ABCDEFGHJKMNPQRSTVWXYZ", m2)]:
            run_dir = runs_dir / run_id
            run_dir.mkdir(parents=True)
            # Create the output files so local verification passes
            (run_dir / "img.png").write_bytes(b"fake image for verification")
            (run_dir / "manifest.json").write_text(json.dumps(m))

        cases_with_manifests = [
            (experiment["cases"][0], "manifest.json", runs_dir / "00123456789ABCDEFGHJKMNPQR"),
            (experiment["cases"][1], "manifest.json", runs_dir / "1789ABCDEFGHJKMNPQRSTVWXYZ"),
        ]

        review = build_normalized_review(
            experiment=experiment,
            cases_with_manifests=cases_with_manifests,
        )

        # Validate the generated review
        validated = validate_review(review)
        assert validated["experiment_id"] == "multi-test"
        assert len(validated["cases"]) == 2
        assert validated["cases"][0]["provider"] == "fal"
        assert validated["cases"][1]["provider"] == "openai"

    def test_includes_experiment_context(self, tmp_path):
        """review must include title, question, hypotheses, factors, rubric."""
        experiment = {
            "schema_version": 1,
            "experiment_id": "ctx-test",
            "project_slug": "test",
            "title": "Context Test",
            "question": "What?",
            "hypotheses": [{"id": "h-1", "claim": "Test", "status": "provisional"}],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "R", "scale": {"min": 1, "max": 5}}],
            "cases": [],
            "created": "2026-07-27T00:00:00Z",
        }

        review = build_normalized_review(
            experiment=experiment,
            cases_with_manifests=[],
        )

        assert review["title"] == "Context Test"
        assert review["question"] == "What?"
        assert len(review["hypotheses"]) == 1
        assert len(review["factors"]) == 1
        assert len(review["rubric"]) == 1
        assert review["created"] == "2026-07-27T00:00:00Z"

    def test_unreadable_manifest_source_hash_absent(self, tmp_path):
        """Unreadable manifest must not have content_hash: None."""
        experiment = {
            "schema_version": 1,
            "experiment_id": "unread-test",
            "project_slug": "test",
            "title": "Unreadable",
            "question": "Q",
            "hypotheses": [],
            "factors": [{"id": "f", "values": ["a"]}],
            "rubric": [{"id": "r", "label": "R", "scale": {"min": 1, "max": 5}}],
            "cases": [
                {
                    "case_id": "c1",
                    "label": "C1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "factors": {"f": "a"},
                    "relationship": {"type": "baseline", "case_id": None},
                }
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        # Point to a non-existent directory
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        cases_with_manifests = [
            (experiment["cases"][0], "manifest.json", runs_dir / "00123456789ABCDEFGHJKMNPQR"),
        ]

        review = build_normalized_review(
            experiment=experiment,
            cases_with_manifests=cases_with_manifests,
        )

        sm = review["cases"][0].get("source_manifest", {})
        assert sm.get("path") == "manifest.json"
        # Must NOT have content_hash: None
        if "content_hash" in sm:
            assert sm["content_hash"] is not None, "content_hash must not be None"


# ── Build diagnostics ──────────────────────────────────────────────────────

class TestBuildDiagnostics:
    def test_detects_duplicate_outputs(self):
        review = {
            "schema_version": 1,
            "experiment_id": "dup-test",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [{"path": "a.png", "content_hash": "sha256:" + "a" * 64}],
                },
                {
                    "case_id": "c2",
                    "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [{"path": "b.png", "content_hash": "sha256:" + "a" * 64}],
                },
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        diag = build_diagnostics(review)
        validated = validate_diagnostics(diag)

        assert validated["total_cases"] == 2
        assert len(validated["duplicate_output_groups"]) == 1
        dup = validated["duplicate_output_groups"][0]
        assert set(dup["case_ids"]) == {"c1", "c2"}

    def test_detects_input_echo(self):
        review = {
            "schema_version": 1,
            "experiment_id": "echo-test",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [
                        {
                            "ordinal": 1,
                            "role": "motion_reference",
                            "path": "in.mp4",
                            "content_hash": "sha256:" + "c" * 64,
                        }
                    ],
                    "outputs": [
                        {"path": "out.mp4", "content_hash": "sha256:" + "c" * 64}
                    ],
                },
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        diag = build_diagnostics(review)
        validated = validate_diagnostics(diag)

        assert len(validated["input_echo_cases"]) == 1
        assert validated["input_echo_cases"][0]["case_id"] == "c1"

    def test_status_counts(self):
        review = {
            "schema_version": 1,
            "experiment_id": "count-test",
            "cases": [
                {
                    "case_id": "c1",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [],
                },
                {
                    "case_id": "c2",
                    "run_id": "1789ABCDEFGHJKMNPQRSTVWXYZ",
                    "status": "failed",
                    "error": "x",
                    "inputs": [],
                    "outputs": [],
                },
                {
                    "case_id": "c3",
                    "run_id": "2EFGHJKMNPQRSTVWXYZabcdefg",
                    "status": "completed",
                    "inputs": [],
                    "outputs": [],
                },
            ],
            "created": "2026-07-27T00:00:00Z",
        }

        diag = build_diagnostics(review)
        assert diag["status_counts"]["completed"] == 2
        assert diag["status_counts"]["failed"] == 1


# ── Regression tests for G1 findings ───────────────────────────────────────

class TestNormalizeRegression:
    def test_generic_kind_returns_unknown_provider(self, tmp_path):
        """generation.generate_image without 'fal' must not be inferred as fal."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image",
            "modality": "image",
            "model": "some-model",
            "mode_used": "t2i",
            "model_actual": "some-model",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{"path": "img.png", "content_hash": "sha256:" + "a" * 64}],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "generic-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "Generic",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        assert result["provider"] == "unknown"

    def test_source_urls_are_redacted(self, tmp_path):
        """source_urls must become counts, never strings."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [],
            "source_urls": [
                "https://storage.googleapis.com/bucket/output.png?Expires=999999&Signature=signed&Key-Pair-Id=APKAI",
                "https://user:token@cdn.example.com/file.mp4",
            ],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "redact-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "Redact",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        # No URL strings at all
        assert "_diagnostic_source_urls" not in result
        assert result.get("source_url_count") == 2
        assert result.get("source_urls_present") is True
        serialized = json.dumps(result, sort_keys=True)
        assert "https://" not in serialized
        assert "storage.googleapis.com" not in serialized
        assert "cdn.example.com" not in serialized

    def test_no_fabricated_digest(self, tmp_path):
        """A manifest with no content_hash must NOT produce a 64-zero digest."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 1,
            "kind": "discord_browser.generate",
            "inputs": {"prompt": "test"},
            "outputs": [{"path": "outputs/img.png"}],
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "nofab-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "NoFab",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        for output in result["outputs"]:
            if "content_hash" in output:
                assert output["content_hash"] != "sha256:" + "0" * 64, (
                    "Fabricated digest detected"
                )


# ── Blocker 1: local media verification ────────────────────────────────────

class TestLocalMediaVerification:
    """Gate G1 Blocker 1 — verify local artifact evidence."""

    def test_verified_image_file(self, tmp_path):
        """An existing image file is verified with real SHA-256 and media type."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        img_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        (run_dir / "test.png").write_bytes(img_content)

        result = _verify_artifact("test.png", run_dir)
        assert result["verified"] is True
        assert result["local_content_hash"].startswith("sha256:")
        assert result["local_content_hash"] != "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result.get("media_type") == "image/png"

    def test_verified_video_file(self, tmp_path):
        """An existing video file is verified with media type."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "clip.mp4").write_bytes(b"fake mp4 content")

        result = _verify_artifact("clip.mp4", run_dir)
        assert result["verified"] is True
        assert "media_type" in result
        assert result["media_type"] == "video/mp4"

    def test_verified_audio_file(self, tmp_path):
        """An existing audio file is verified with media type."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "sound.mp3").write_bytes(b"fake mp3 content")

        result = _verify_artifact("sound.mp3", run_dir)
        assert result["verified"] is True
        assert result.get("media_type") == "audio/mpeg"

    def test_missing_file_not_verified(self, tmp_path):
        """Missing file is not verified and records a capture gap."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        result = _verify_artifact("nonexistent.png", run_dir)
        assert result["verified"] is False
        assert len(result["capture_gaps"]) > 0
        assert any("not found" in g["detail"] for g in result["capture_gaps"])

    def test_digest_mismatch_recorded(self, tmp_path):
        """When reported hash differs from local, both are preserved with warning."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        file_content = b"specific content for hash mismatch test"
        (run_dir / "output.png").write_bytes(file_content)

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{
                "path": "output.png",
                "content_hash": "sha256:deadbeef" + "0" * 56,
            }],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "mismatch-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "Mismatch",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        out = result["outputs"][0]
        assert out["verified"] is True
        # content_hash is the verified local digest
        assert out["content_hash"].startswith("sha256:")
        assert out["content_hash"] != "sha256:deadbeef" + "0" * 56
        # reported_content_hash preserves the manifest's claim
        assert out["reported_content_hash"] == "sha256:deadbeef" + "0" * 56
        # mismatch warning in capture gaps
        mismatch_gaps = [g for g in result["capture_gaps"] if "differs from verified" in g.get("detail", "")]
        assert len(mismatch_gaps) >= 1

    def test_symlink_escape_blocked(self, tmp_path):
        """Path that escapes via symlink is not verified."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "evil.txt").write_text("escaped!")
        # Create a symlink inside run_dir pointing outside
        symlink_path = run_dir / "escape_link"
        symlink_path.symlink_to(outside_dir / "evil.txt")

        result = _verify_artifact("escape_link", run_dir)
        # The symlink resolves outside run_dir — should not be verified
        assert result["verified"] is False
        assert any("escapes" in g["detail"] for g in result["capture_gaps"])

    def test_media_type_present_but_hash_absent(self, tmp_path):
        """When media_type exists but content_hash is absent, renderer gate blocks playback."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "image.png").write_bytes(b"fake png content")

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{
                "path": "image.png",
                # No content_hash — manifest didn't supply one
                "media_type": "image/png",
            }],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "media-no-hash-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "MediaNoHash",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        out = result["outputs"][0]
        # File exists, verified=True, local content_hash computed
        assert out["verified"] is True
        assert "content_hash" in out  # local hash was computed
        assert out["content_hash"].startswith("sha256:")
        # media_type from manifest preserved
        assert out.get("media_type") == "image/png"

    def test_media_type_present_no_file_unverified(self, tmp_path):
        """When media_type exists but file is missing, entry is NOT verified."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # No file created

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{
                "path": "image.png",
                "content_hash": "sha256:" + "a" * 64,
                "media_type": "image/png",
            }],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "missing-file-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "MissingFile",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        out = result["outputs"][0]
        assert out["verified"] is False
        # Hash moved to reported_content_hash only
        assert "content_hash" not in out or out.get("content_hash") is None
        assert out.get("reported_content_hash") == "sha256:" + "a" * 64

    def test_repeated_normalization_produces_identical_bytes(self, tmp_path):
        """Repeated normalization with verified files produces byte-identical results."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        file_content = b"deterministic verification test content"
        (run_dir / "img.png").write_bytes(file_content)

        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-dev",
            "mode_used": "t2i",
            "model_actual": "fal-ai/flux/dev",
            "execution": "cloud",
            "request": {"prompt": "test", "seed": 1, "count": 1},
            "outputs": [{
                "path": "img.png",
                "content_hash": "sha256:" + "b" * 64,
            }],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {
            "case_id": "det-verify-1",
            "run_id": "00123456789ABCDEFGHJKMNPQR",
            "label": "DetVerify",
            "factors": {"method": "a"},
            "relationship": {"type": "baseline", "case_id": None},
        }
        r1 = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        r2 = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case=case,
            run_path=run_dir,
        )
        assert r1 == r2
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

    def test_non_regular_file_not_verified(self, tmp_path):
        """Directories and non-regular files are not verified."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "subdir").mkdir()

        result = _verify_artifact("subdir", run_dir)
        assert result["verified"] is False
        assert any("not a regular file" in g["detail"] for g in result["capture_gaps"])


# ── Phase 3: requested/applied/dropped features and ComfyUI preservation ────

class TestRequestedFeatures:
    def test_v2_requested_features_extracted(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "out.png").write_bytes(b"x")
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "modality": "image",
            "model": "flux-pro",
            "mode_used": "i2i",
            "execution": "cloud",
            "request": {"prompt": "p", "seed": 1, "negative_prompt": "blurry", "size": "1024x1024"},
            "outputs": [{"path": "out.png", "content_hash": "sha256:" + "a" * 64}],
            "applied_features": ["seed"],
            "dropped_features": ["negative_prompt"],
            "seed": 1,
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
            "inputs": {},
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        case = {"case_id": "c1", "run_id": "00123456789ABCDEFGHJKMNPQR"}
        result = normalize_case_from_manifest(
            manifest=manifest, manifest_path="manifest.json", case=case, run_path=run_dir,
        )
        assert "requested_features" in result
        assert "seed" in result["requested_features"]
        assert "negative_prompt" in result["requested_features"]
        assert result["applied_features"] == ["seed"]
        assert result["dropped_features"] == ["negative_prompt"]


class TestComfyUIPreservation:
    def test_workflow_and_params_preserved(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 1,
            "kind": "vibecomfy.run",
            "inputs": {
                "workflow": "workflows/desert.json",
                "prompt": "desert time-lapse",
                "seed": 12345,
                "steps": 30,
                "cfg": 7.0,
            },
            "outputs": [{"path": "out.mp4", "content_hash": "sha256:" + "a" * 64, "media_type": "video/mp4"}],
            "created": "2026-07-27T00:00:00Z",
            "warnings": [],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        (run_dir / "out.mp4").write_bytes(b"mp4")
        case = {"case_id": "c1", "run_id": "00123456789ABCDEFGHJKMNPQR"}
        result = normalize_case_from_manifest(
            manifest=manifest, manifest_path="manifest.json", case=case, run_path=run_dir,
        )
        assert result["provider"] == "comfyui"
        # Workflow preserved as an input with the workflow role.
        assert any(inp.get("role") == "workflow" for inp in result["inputs"])
        # ComfyUI parameters surfaced under parameters.
        assert result["parameters"].get("steps") == 30
        assert result["parameters"].get("cfg") == 7.0
        # Workflow path recorded under a clearly-labelled provider extension.
        assert result["provider_extension"]["comfyui"]["workflow_path"] == "workflows/desert.json"


class TestGateG3AdversarialNormalization:
    def test_build_review_does_not_read_escaping_manifest_symlink(
        self, tmp_path, monkeypatch
    ):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        outside_manifest = tmp_path / "outside-manifest.json"
        outside_manifest.write_text(json.dumps({
            "schema_version": 1,
            "kind": "local.generate",
            "inputs": {"prompt": "outside"},
            "outputs": [],
            "status": "completed",
        }))
        (run_dir / "manifest.json").symlink_to(outside_manifest)
        original_read_bytes = Path.read_bytes

        def guarded_read_bytes(path):
            if path.resolve() == outside_manifest.resolve():
                pytest.fail("escaping source manifest bytes were read")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
        review = build_normalized_review(
            experiment={
                "experiment_id": "containment",
                "created": "2026-07-27T00:00:00Z",
            },
            cases_with_manifests=[(
                {
                    "case_id": "escaped",
                    "run_id": "00123456789ABCDEFGHJKMNPQR",
                },
                "manifest.json",
                run_dir,
            )],
        )
        case = review["cases"][0]
        assert case["status"] == "failed"
        assert case["source_manifest"]["verified"] is False
        assert "outside the run directory" in case["error"]

    def test_boolean_manifest_schema_version_is_not_v1(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": True,
            "kind": "local.generate",
            "inputs": {"prompt": "must not normalize"},
            "outputs": [],
            "status": "completed",
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case={"case_id": "bool", "run_id": "00123456789ABCDEFGHJKMNPQR"},
            run_path=run_dir,
        )
        assert result["status"] == "failed"
        assert result["provider"] == "unknown"
        assert result["prompt"] is None
        assert "integer schema_version" in result["error"]

    def test_adapter_capture_gaps_survive_normalization(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest = {
            "schema_version": 1,
            "kind": "discord_browser.generate",
            "inputs": {"prompt": "known prompt"},
            "outputs": [],
            "status": "partial",
            "capture_gaps": [{
                "kind": "ambiguous_provenance",
                "detail": "terminal provider response was not captured",
            }],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case={"case_id": "c1", "run_id": "00123456789ABCDEFGHJKMNPQR"},
            run_path=run_dir,
        )
        assert {
            "kind": "ambiguous_provenance",
            "detail": "terminal provider response was not captured",
        } in result["capture_gaps"]

    def test_managed_manifest_recursively_redacted_and_contradiction_is_partial(
        self, tmp_path
    ):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "out.png").write_bytes(b"x")
        manifest = {
            "schema_version": 2,
            "kind": "generation.generate_image_fal",
            "status": "completed",
            "error": "Authorization: Bearer sk-live-secret",
            "request": {
                "prompt": "use https://cdn.invalid/x?token=TOPSECRET",
                "custom_knob": "preserved",
                "api_key": "RAWSECRET",
            },
            "outputs": [{"path": "out.png"}],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest))
        result = normalize_case_from_manifest(
            manifest=manifest,
            manifest_path="manifest.json",
            case={"case_id": "c1", "run_id": "00123456789ABCDEFGHJKMNPQR"},
            run_path=run_dir,
        )
        serialized = json.dumps(result)
        assert "TOPSECRET" not in serialized
        assert "RAWSECRET" not in serialized
        assert "sk-live-secret" not in serialized
        assert result["request"]["custom_knob"] == "preserved"
        assert result["status"] == "partial"

    def test_provider_tokens_do_not_false_match(self):
        assert _provider_from_kind("generation.fallback") == "unknown"
        assert _provider_from_kind("tool.discordant") == "unknown"
        assert _provider_from_kind("tool.relocalize") == "unknown"

    def test_duplicate_within_one_case_is_not_cross_case_group(self):
        digest = "sha256:" + "a" * 64
        review = {
            "schema_version": 1,
            "experiment_id": "x",
            "cases": [{
                "case_id": "c1",
                "outputs": [{"content_hash": digest}, {"content_hash": digest}],
            }],
        }
        assert build_diagnostics(review)["duplicate_output_groups"] == []
