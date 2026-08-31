"""Focused tests for T26: partial-output manifest on generate_image_openai loop failure.

Validates:
- When generate_image_openai's API fails after producing at least one output,
  the manifest.json is atomically written with the partial successful outputs.
- The original exception is preserved and re-raised.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.packs.generation.executors.generate_image_openai.run import (
    generate as openai_generate,
)


class TestPartialOutputManifestOnOpenAILoopFailure:
    """T26: When the OpenAI generation loop fails after partial success, manifest is written."""

    def test_partial_output_manifest_atomic_write_and_original_exception_reraised(
        self, tmp_path: Path,
    ) -> None:
        """API succeeds on job 0, fails on job 1.

        The manifest must be atomically written with job 0's output,
        and the original AstridError must be re-raised.
        """
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"

        # --- mock API response for first (successful) job ------------------
        response_ok = {
            "data": [{"b64_json": "dGVzdA=="}],  # base64 "test"
            "usage": {"total_tokens": 100},
            "created": 1700000000,
        }

        # --- build args namespace with two jobs ---------------------------
        import argparse

        args = argparse.Namespace()
        args.prompt = ["first prompt", "second prompt"]
        args.prompts_file = None
        args.preset = None
        args.model = "gpt-image-2"
        args.n = 1
        args.size = "1024x1024"
        args.quality = "medium"
        args.output_format = "png"
        args.output_compression = None
        args.background = None
        args.moderation = None
        args.out_dir = out_dir
        args.manifest = manifest_path
        args.env_file = None
        args.timeout = 180
        args.force = False
        args.dry_run = False
        args.no_open = True

        with patch(
            "astrid.packs.generation.executors.generate_image_openai.run._call_image_api",
            side_effect=[
                response_ok,
                AstridError("simulated API failure"),
            ],
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run._resolve_key",
            return_value="test-api-key",
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run.write_json_atomic",
        ) as mock_write:
            # --- act: should raise the original AstridError ----------------
            with pytest.raises(AstridError, match="simulated API failure"):
                openai_generate(args)

            # --- assert: manifest was atomically written with partial outputs
            mock_write.assert_called_once()
            (path_arg, manifest_data) = mock_write.call_args[0]
            assert path_arg == manifest_path
            assert isinstance(manifest_data, dict), f"expected dict, got {type(manifest_data)}"
            assert manifest_data.get("schema_version") == 2
            assert manifest_data.get("kind") == "generation.generate_image_openai"
            assert "jobs" in manifest_data
            assert len(manifest_data["jobs"]) == 1, "manifest must contain exactly one partial job"
            job0 = manifest_data["jobs"][0]
            assert job0["prompt"] == "first prompt"
            assert len(job0["outputs"]) == 1
            assert job0["outputs"][0].startswith(str(out_dir))
            assert job0["usage"] == {"total_tokens": 100}
            assert job0["created"] == 1700000000

    def test_no_manifest_written_when_no_outputs_produced(
        self, tmp_path: Path,
    ) -> None:
        """When the very first API call fails, no manifest is written."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"

        import argparse

        args = argparse.Namespace()
        args.prompt = ["only prompt"]
        args.prompts_file = None
        args.preset = None
        args.model = "gpt-image-2"
        args.n = 1
        args.size = "1024x1024"
        args.quality = "medium"
        args.output_format = "png"
        args.output_compression = None
        args.background = None
        args.moderation = None
        args.out_dir = out_dir
        args.manifest = manifest_path
        args.env_file = None
        args.timeout = 180
        args.force = False
        args.dry_run = False
        args.no_open = True

        with patch(
            "astrid.packs.generation.executors.generate_image_openai.run._call_image_api",
            side_effect=AstridError("first call failure"),
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run._resolve_key",
            return_value="test-api-key",
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run.write_json_atomic",
        ) as mock_write:
            with pytest.raises(AstridError, match="first call failure"):
                openai_generate(args)

            # No manifest should be written when zero outputs were produced.
            mock_write.assert_not_called()

    def test_manifest_content_matches_success_path_equivalent(
        self, tmp_path: Path,
    ) -> None:
        """Partial-output manifest has the same list-of-dicts shape as a success-path manifest."""
        response_ok = {
            "data": [{"b64_json": "dGVzdA=="}],
            "usage": {"total_tokens": 100},
            "created": 1700000000,
        }

        # --- mock API: succeed once, fail on second -----------------------
        import argparse

        # --- partial path: two jobs, one success then failure --------------
        out_dir_partial = tmp_path / "out_partial"
        out_dir_partial.mkdir()
        args_partial = argparse.Namespace()
        args_partial.prompt = ["prompt A", "prompt B"]
        args_partial.prompts_file = None
        args_partial.preset = None
        args_partial.model = "gpt-image-2"
        args_partial.n = 1
        args_partial.size = "1024x1024"
        args_partial.quality = "medium"
        args_partial.output_format = "png"
        args_partial.output_compression = None
        args_partial.background = None
        args_partial.moderation = None
        args_partial.out_dir = out_dir_partial
        args_partial.manifest = tmp_path / "manifest_partial.json"
        args_partial.env_file = None
        args_partial.timeout = 180
        args_partial.force = False
        args_partial.dry_run = False
        args_partial.no_open = True

        # --- full success path: one job, one success ----------------------
        out_dir_full = tmp_path / "out_full"
        out_dir_full.mkdir()
        args_full = argparse.Namespace()
        args_full.prompt = ["prompt A"]
        args_full.prompts_file = None
        args_full.preset = None
        args_full.model = "gpt-image-2"
        args_full.n = 1
        args_full.size = "1024x1024"
        args_full.quality = "medium"
        args_full.output_format = "png"
        args_full.output_compression = None
        args_full.background = None
        args_full.moderation = None
        args_full.out_dir = out_dir_full
        args_full.manifest = tmp_path / "manifest_full.json"
        args_full.env_file = None
        args_full.timeout = 180
        args_full.force = False
        args_full.dry_run = False
        args_full.no_open = True

        # --- get partial manifest via exception path ----------------------
        captured_partial: list = []

        def _capture_partial(path, data):
            captured_partial.append(data)

        with patch(
            "astrid.packs.generation.executors.generate_image_openai.run._call_image_api",
            side_effect=[
                response_ok,
                AstridError("fail"),
            ],
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run._resolve_key",
            return_value="test-api-key",
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run.write_json_atomic",
            side_effect=_capture_partial,
        ):
            with pytest.raises(AstridError, match="fail"):
                openai_generate(args_partial)

        assert len(captured_partial) == 1
        partial_manifest = captured_partial[0]

        # --- get full success manifest -----------------------------------
        captured_full: list = []

        def _capture_full(path, data):
            captured_full.append(data)

        with patch(
            "astrid.packs.generation.executors.generate_image_openai.run._call_image_api",
            return_value=response_ok,
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run._resolve_key",
            return_value="test-api-key",
        ), patch(
            "astrid.packs.generation.executors.generate_image_openai.run.write_json_atomic",
            side_effect=_capture_full,
        ):
            openai_generate(args_full)

        assert len(captured_full) == 1
        full_manifest = captured_full[0]

        # --- compare shapes: both are v2 universal manifest dicts with same job entry structure
        assert isinstance(partial_manifest, dict)
        assert isinstance(full_manifest, dict)
        assert partial_manifest.get("schema_version") == 2
        assert full_manifest.get("schema_version") == 2
        assert partial_manifest.get("kind") == "generation.generate_image_openai"
        assert full_manifest.get("kind") == "generation.generate_image_openai"
        assert len(partial_manifest["jobs"]) == len(full_manifest["jobs"]) == 1

        partial_job = partial_manifest["jobs"][0]
        full_job = full_manifest["jobs"][0]
        assert set(partial_job.keys()) == set(full_job.keys()), (
            f"partial keys {set(partial_job.keys())} != "
            f"full keys {set(full_job.keys())}"
        )
        assert partial_job["prompt"] == full_job["prompt"]
        assert isinstance(partial_job["outputs"], list)
        assert len(partial_job["outputs"]) == len(full_job["outputs"]) == 1
        assert partial_job["usage"] == full_job["usage"]
        assert partial_job["created"] == full_job["created"]
        assert partial_job["request"]["model"] == full_job["request"]["model"]
